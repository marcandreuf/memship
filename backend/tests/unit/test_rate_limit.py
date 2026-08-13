"""The sliding window itself, without HTTP in the way."""

import time

import pytest
from fastapi import HTTPException

from app.core.security.rate_limit import (
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
            throttle.record(f"user{i}@test.com")
        assert len(throttle._hits) == 50

        time.sleep(1.05)
        throttle.record("someone-else@test.com")

        assert len(throttle._hits) == 1


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
    @pytest.mark.parametrize("raw", ["User@Test.com", " user@test.com ", "USER@TEST.COM"])
    def test_casing_and_padding_share_one_bucket(self, raw):
        assert identity_key(raw) == "user@test.com"


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
