"""The auth throttles count in Redis, shared by every API process (#210).

With the counters in process, each API worker or replica kept its own window,
so N processes silently allowed N times every limit. The case that matters is
`test_two_processes_share_one_budget`; the rest pin the Redis window to the same
semantics the in-process one had.
"""

import time

import pytest

from app.core.security import rate_limit
from app.core.security.rate_limit import Throttle


@pytest.fixture(autouse=True)
def _redis_reachable(monkeypatch):
    """Fail rather than quietly pass on the in-process fallback."""
    monkeypatch.setattr(rate_limit, "_redis_down_until", 0.0)
    rate_limit._connect().client.ping()


@pytest.fixture
def make():
    made = []

    def _make(name="redis-test", *, limit=3, window_seconds=60):
        throttle = Throttle(name, limit=limit, window_seconds=window_seconds)
        throttle.reset()
        made.append(throttle)
        return throttle

    yield _make
    for throttle in made:
        throttle.reset()


def _client():
    return rate_limit._connect().client


class TestSharedBetweenProcesses:
    def test_two_processes_share_one_budget(self, make):
        """Two `Throttle` objects with one name are what two API processes each
        hold. Hits recorded through either must count against both."""
        worker_a = make()
        worker_b = Throttle(worker_a.name, limit=3, window_seconds=60)

        worker_a.record("k")
        worker_b.record("k")
        worker_a.record("k")

        assert worker_a.retry_after("k") > 0
        assert worker_b.retry_after("k") > 0

    def test_the_counts_are_in_redis_not_in_process(self, make):
        throttle = make()
        throttle.record("k")

        assert _client().zcard(throttle._key("k")) == 1
        assert throttle._local._hits == {}


class TestTheWindow:
    def test_hits_below_the_limit_are_allowed(self, make):
        throttle = make()
        for _ in range(3):
            assert throttle.retry_after("k") == 0
            throttle.record("k")

        assert throttle.retry_after("k") > 0

    def test_checking_does_not_spend_the_budget(self, make):
        throttle = make()
        for _ in range(10):
            assert throttle.retry_after("k") == 0

    def test_hits_in_the_same_instant_each_count(self, make):
        throttle = make(limit=50)
        for _ in range(50):
            throttle.record("k")

        assert _client().zcard(throttle._key("k")) == 50

    def test_retry_after_is_the_time_until_the_oldest_hit_leaves(self, make):
        throttle = make(limit=1, window_seconds=600)
        throttle.record("k")

        assert 595 <= throttle.retry_after("k") <= 601

    def test_the_window_slides(self, make):
        throttle = make(limit=2, window_seconds=1)
        throttle.record("k")
        throttle.record("k")
        assert throttle.retry_after("k") > 0

        time.sleep(1.05)

        assert throttle.retry_after("k") == 0

    def test_keys_expire_so_caller_supplied_ones_cannot_accumulate(self, make):
        throttle = make(window_seconds=60)
        throttle.record("someone@examplee6e3b1.com")

        assert 0 < _client().ttl(throttle._key("someone@examplee6e3b1.com")) <= 61

    def test_clear_forgets_one_key_only(self, make):
        throttle = make()
        for _ in range(3):
            throttle.record("a")
            throttle.record("b")

        throttle.clear("a")

        assert throttle.retry_after("a") == 0
        assert throttle.retry_after("b") > 0


class TestReset:
    def test_reset_touches_only_its_own_throttle(self, make):
        mine = make("redis-test-mine")
        other = make("redis-test-other")
        for _ in range(3):
            mine.record("k")
            other.record("k")

        mine.reset()

        assert mine.retry_after("k") == 0
        assert other.retry_after("k") > 0

    def test_reset_leaves_keys_outside_the_prefix_alone(self, make):
        """The database is shared with the Celery broker."""
        throttle = make()
        _client().set("memship-unrelated-key", "1")
        try:
            throttle.record("k")
            throttle.reset()

            assert _client().get("memship-unrelated-key") == b"1"
        finally:
            _client().delete("memship-unrelated-key")
