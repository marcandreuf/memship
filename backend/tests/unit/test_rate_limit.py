"""The sliding window itself, without HTTP in the way.

These run against the in-process fallback window: the CI unit job has no Redis.
The Redis-backed window is covered in tests/integration/test_rate_limit_redis.py.
"""

import logging
import math
import time
from pathlib import Path

import pytest
import redis
from fastapi import HTTPException

from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.security import rate_limit
from app.core.security.rate_limit import (
    REGISTER_BY_IP,
    Throttle,
    client_ip,
    enforce,
    identity_key,
    record,
)


class _Client:
    def __init__(self, host):
        self.host = host


class _Request:
    """The two attributes ``client_ip`` reads."""

    def __init__(self, host="10.0.0.1", forwarded=None):
        self.client = _Client(host) if host else None
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}


@pytest.fixture(autouse=True)
def _local_window_only(monkeypatch):
    """Hold the Redis backoff open, so every call uses the in-process window."""
    monkeypatch.setattr(rate_limit, "_redis_down_until", math.inf)
    monkeypatch.setattr(rate_limit, "_degraded", False)


@pytest.fixture
def throttle():
    return Throttle("test", limit=3, window_seconds=60)


class TestTheWindow:
    def test_hits_below_the_limit_are_allowed(self, throttle):
        for _ in range(3):
            assert throttle.retry_after("k") == 0
            throttle.record("k")

    def test_the_limit_is_the_number_of_hits_not_the_number_of_checks(self, throttle):
        """``retry_after`` is a read. Checking ten times without recording must
        not itself exhaust the budget — the login path checks before it knows
        whether the attempt failed."""
        for _ in range(10):
            assert throttle.retry_after("k") == 0

    def test_the_next_hit_after_the_limit_is_refused(self, throttle):
        for _ in range(3):
            throttle.record("k")

        assert throttle.retry_after("k") > 0

    def test_keys_are_counted_separately(self, throttle):
        for _ in range(3):
            throttle.record("a")

        assert throttle.retry_after("a") > 0
        assert throttle.retry_after("b") == 0

    def test_retry_after_never_reports_zero_while_blocked(self, throttle):
        for _ in range(3):
            throttle.record("k")

        assert throttle.retry_after("k") >= 1

    def test_the_window_slides(self):
        throttle = Throttle("fast", limit=2, window_seconds=1)
        throttle.record("k")
        throttle.record("k")
        assert throttle.retry_after("k") > 0

        time.sleep(1.05)

        assert throttle.retry_after("k") == 0

    def test_clear_forgets_one_key_only(self, throttle):
        for _ in range(3):
            throttle.record("a")
            throttle.record("b")

        throttle.clear("a")

        assert throttle.retry_after("a") == 0
        assert throttle.retry_after("b") > 0

    def test_expired_keys_are_swept_so_the_map_cannot_grow_without_bound(self):
        """Keys are caller-supplied addresses, so a run against invented ones
        must not accumulate for the life of the process."""
        throttle = Throttle("sweep", limit=5, window_seconds=1)
        for i in range(50):
            throttle.record(f"user{i}@examplee6e3b1.com")
        assert len(throttle._local._hits) == 50

        time.sleep(1.05)
        throttle.record("someone-else@examplee6e3b1.com")

        assert len(throttle._local._hits) == 1


class _Unreachable:
    """Stands in for `_connect()`'s result: every script call fails as Redis would."""

    def __init__(self):
        self.calls = 0

    def _fail(self, *args, **kwargs):
        self.calls += 1
        raise redis.ConnectionError("Connection refused")

    retry_after = record = _fail


class TestRedisUnavailable:
    """Chosen behaviour for #210: degrade to the per-process window and say so,
    rather than refusing every sign-in or dropping the limit."""

    @pytest.fixture
    def unreachable(self, monkeypatch):
        backend = _Unreachable()
        monkeypatch.setattr(rate_limit, "_connect", lambda: backend)
        monkeypatch.setattr(rate_limit, "_redis_down_until", 0.0)
        return backend

    def test_the_limit_still_holds_per_process(self, unreachable, throttle):
        for _ in range(3):
            throttle.record("k")

        assert throttle.retry_after("k") > 0

    def test_the_fallback_is_logged_as_an_error(self, unreachable, throttle, caplog):
        with caplog.at_level(logging.ERROR, logger=rate_limit.__name__):
            throttle.retry_after("k")

        assert any("cannot reach Redis" in r.getMessage() for r in caplog.records)

    def test_redis_is_not_retried_on_every_request_during_an_outage(
        self, unreachable, throttle
    ):
        """An outage costs one connection attempt per backoff interval, not
        several per login."""
        for _ in range(10):
            throttle.record("k")
            throttle.retry_after("k")

        assert unreachable.calls == 1

    def test_recovery_is_logged(self, unreachable, throttle, monkeypatch, caplog):
        throttle.retry_after("k")

        class _Back:
            def retry_after(self, *args, **kwargs):
                return 0

        monkeypatch.setattr(rate_limit, "_connect", lambda: _Back())
        monkeypatch.setattr(rate_limit, "_redis_down_until", 0.0)
        with caplog.at_level(logging.WARNING, logger=rate_limit.__name__):
            assert throttle.retry_after("k") == 0

        assert any("reached Redis again" in r.getMessage() for r in caplog.records)


class TestEnforce:
    def test_it_passes_when_every_key_is_under_its_limit(self, throttle):
        enforce((throttle, "a"), (throttle, "b"))

    def test_it_raises_429_with_retry_after(self, throttle):
        record(*[(throttle, "a")] * 3)

        with pytest.raises(HTTPException) as excinfo:
            enforce((throttle, "a"))

        assert excinfo.value.status_code == 429
        assert int(excinfo.value.headers["Retry-After"]) >= 1

    def test_it_reports_the_longest_wait_of_all_the_keys(self):
        short = Throttle("short", limit=1, window_seconds=2)
        long = Throttle("long", limit=1, window_seconds=600)
        short.record("k")
        long.record("k")

        with pytest.raises(HTTPException) as excinfo:
            enforce((short, "k"), (long, "k"))

        assert int(excinfo.value.headers["Retry-After"]) > 500


class TestIdentityKey:
    @pytest.mark.parametrize(
        "raw",
        [
            "User@Examplee6e3b1.com",
            " user@examplee6e3b1.com ",
            "USER@EXAMPLEE6E3B1.COM",
        ],
    )
    def test_casing_and_padding_share_one_bucket(self, raw):
        assert identity_key(raw) == "user@examplee6e3b1.com"


class TestClientIp:
    def test_it_falls_back_to_the_socket_when_there_is_no_proxy(self):
        assert client_ip(_Request(host="10.0.0.1")) == "10.0.0.1"

    def test_it_takes_the_rightmost_forwarded_hop(self):
        """Caddy appends the peer it accepted, so the rightmost entry is the one
        a proxy wrote and everything left of it is caller-supplied."""
        request = _Request(host="172.18.0.2", forwarded="203.0.113.9")

        assert client_ip(request) == "203.0.113.9"

    def test_a_spoofed_hop_cannot_displace_the_one_the_proxy_wrote(self):
        request = _Request(host="172.18.0.2", forwarded="1.2.3.4, 203.0.113.9")

        assert client_ip(request) == "203.0.113.9"

    def test_a_missing_client_does_not_raise(self):
        assert client_ip(_Request(host=None)) == "unknown"


class TestClientIpBehindMoreThanOneProxy:
    """`TRUSTED_PROXY_HOPS` states how deep the chain is, because a request does
    not reveal it. Every case here is one proxy chain read with the right and the
    wrong count (#59)."""

    # Caller -> CDN -> Caddy -> API. The CDN appends the caller, Caddy appends
    # the CDN, so the caller is two entries from the right.
    TWO_HOPS = "198.51.100.7, 203.0.113.9"

    def test_the_caller_is_found_when_the_count_matches_the_chain(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)
        request = _Request(host="172.18.0.2", forwarded=self.TWO_HOPS)

        assert client_ip(request) == "198.51.100.7"

    def test_one_hop_too_few_buckets_the_whole_site_together(self, monkeypatch):
        """The failure #59 describes: the rightmost entry is the inner proxy, so
        every caller shares one key and `LOGIN_BY_IP` throttles everybody at
        once. Asserted so the reason for the setting cannot be optimised away."""
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
        alice = _Request(host="172.18.0.2", forwarded="198.51.100.7, 203.0.113.9")
        bob = _Request(host="172.18.0.2", forwarded="198.51.100.250, 203.0.113.9")

        assert client_ip(alice) == client_ip(bob) == "203.0.113.9"

    def test_a_chain_shorter_than_configured_falls_back_to_the_socket(self, monkeypatch):
        """Fewer entries than proxies means the request did not come through the
        chain that was described, so nothing in the header is worth trusting."""
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)
        request = _Request(host="172.18.0.2", forwarded="1.2.3.4")

        assert client_ip(request) == "172.18.0.2"

    def test_a_deeper_chain_still_ignores_what_the_caller_supplied(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)
        request = _Request(host="172.18.0.2", forwarded="9.9.9.9, " + self.TWO_HOPS)

        assert client_ip(request) == "198.51.100.7"


class TestClientIpWithNoProxy:
    def test_zero_hops_ignores_the_header_entirely(self, monkeypatch):
        """Published with nothing in front, the whole header is caller-supplied,
        so honouring any of it hands out the throttle key."""
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
        request = _Request(host="203.0.113.9", forwarded="1.2.3.4, 5.6.7.8")

        assert client_ip(request) == "203.0.113.9"

    def test_a_negative_count_is_refused_at_the_boundary(self):
        with pytest.raises(ValidationError):
            Settings(TRUSTED_PROXY_HOPS=-1)


class TestRegistrationLimitSetting:
    """`REGISTER_LIMIT_PER_IP` is raised in the dev stack only (#462)."""

    def test_the_default_is_the_production_limit(self):
        assert Settings.model_fields["REGISTER_LIMIT_PER_IP"].default == 5

    def test_the_throttle_reads_it(self):
        assert REGISTER_BY_IP.limit == settings.REGISTER_LIMIT_PER_IP

    def test_the_production_stack_does_not_forward_it(self):
        compose = Path(__file__).resolve().parents[3] / "docker-compose.yml"
        assert "REGISTER_LIMIT_PER_IP" not in compose.read_text(encoding="utf-8")

    def test_zero_is_refused_at_the_boundary(self):
        with pytest.raises(ValidationError):
            Settings(REGISTER_LIMIT_PER_IP=0)
