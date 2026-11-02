"""Sliding-window throttles for the unauthenticated auth endpoints.

`POST /auth/login` accepted unlimited attempts, and `User.is_locked` — read in
three places — was written by no code path at all, so nothing anywhere slowed a
password guess down. The same held for the two endpoints that send mail to an
arbitrary address on an anonymous request.

**Counters live in Redis**, which the stack already runs for Celery, so every
API process shares one window. They were in-process until #210: correct while
the deployment ran exactly one API process, but a second worker or replica
would each have kept its own count and silently multiplied every limit —
nothing failed or logged, the limit just stopped being one. Redis also keeps
the window across a restart.

If Redis cannot be reached, each throttle falls back to counting in this
process and logs an error. That is the pre-#210 behaviour: still a limit per
process, and sign-in keeps working through an outage that has already stopped
Celery mail. Refusing every sign-in instead would turn a Redis outage into a
site outage; dropping the limit would leave password guessing unbounded for as
long as the outage lasts.

Deliberately *not* done: flipping `users.is_locked` after N failures. That
column is the administrator's own switch, with `locked_reason` next to it, and
writing it from failed logins hands any anonymous caller a way to lock a named
member out permanently by guessing at their address. A window that expires on
its own bounds the same guessing without the denial-of-service.
"""

import logging
import time
import uuid
from collections import deque
from collections.abc import Callable
from functools import cache
from threading import Lock
from typing import NamedTuple, TypeVar

import redis
from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Overridden per xdist worker by tests/integration/conftest.py, so concurrent
# workers sharing one Redis database never read or wipe each other's windows.
KEY_PREFIX = "memship:throttle"

# After a failed call Redis is not tried again for this long, so an outage costs
# one connection attempt per interval rather than several per auth request.
_BACKOFF_SECONDS = 5.0
_redis_down_until = 0.0
_degraded = False

# Both scripts read the clock from Redis `TIME`, so every API process measures
# the window against one clock. Scores are hit times; members are unique tokens
# so two hits in the same microsecond still count twice. A hit at or before
# ``now - window`` has left the window — the same boundary as `_LocalWindow`.
_RETRY_AFTER_LUA = """
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
local window = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if redis.call('ZCARD', KEYS[1]) < tonumber(ARGV[2]) then
    return 0
end
local oldest = tonumber(redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')[2])
return math.max(1, math.floor(oldest + window - now) + 1)
"""

_RECORD_LUA = """
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
local window = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('EXPIRE', KEYS[1], window + 1)
"""


class _Redis(NamedTuple):
    client: redis.Redis
    retry_after: Callable
    record: Callable


@cache
def _connect() -> _Redis:
    # Short timeouts: this is on the login path, and an unreachable Redis has
    # to fall back quickly rather than hold the request.
    client = redis.Redis.from_url(
        settings.CELERY_BROKER_URL, socket_connect_timeout=0.5, socket_timeout=0.5
    )
    return _Redis(
        client,
        client.register_script(_RETRY_AFTER_LUA),
        client.register_script(_RECORD_LUA),
    )


def _shared(operation: Callable[[_Redis], T], fallback: Callable[[], T]) -> T:
    """Run ``operation`` against Redis, or ``fallback`` while it is unreachable."""
    global _redis_down_until, _degraded
    now = time.monotonic()
    if now >= _redis_down_until:
        try:
            result = operation(_connect())
        except redis.RedisError as exc:
            _redis_down_until = now + _BACKOFF_SECONDS
            _degraded = True
            logger.error(
                "Auth throttles cannot reach Redis (%s); counting per process "
                "until it is back, so limits are not shared between API processes.",
                exc,
            )
        else:
            if _degraded:
                _degraded = False
                logger.warning("Auth throttles reached Redis again; limits are shared.")
            return result
    return fallback()


def client_ip(request: Request) -> str:
    """The caller's address, as far as it can be trusted.

    Every documented deployment puts a proxy in front of the API, so
    `request.client.host` is that proxy's address on the compose network and is
    the same for all callers — useless as a key. Each proxy in the chain
    *appends* the peer it accepted to `X-Forwarded-For`, so the caller's own
    address sits ``TRUSTED_PROXY_HOPS`` entries from the right. Anything further
    left was supplied by the caller and is ignored.

    The count is configured because nothing in a request reveals it. Reading the
    rightmost entry is correct for exactly one proxy; with a second hop in front
    — a CDN, a load balancer, an operator's own proxy — it returns that hop's
    address instead, collapsing every caller into one bucket so `LOGIN_BY_IP`
    throttles the whole site at once (#59).

    Two cases fall back to the socket, both meaning "this request did not arrive
    through the deployment that was described, so the header proves nothing":
    ``TRUSTED_PROXY_HOPS = 0``, which is the API published with nothing in front
    and the whole header therefore caller-controlled, and a chain shorter than
    the one configured. The per-identity limits do not depend on any of this.
    """
    socket = request.client.host if request.client else "unknown"
    trusted = settings.TRUSTED_PROXY_HOPS
    if trusted < 1:
        return socket
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if len(hops) >= trusted:
            return hops[-trusted]
    return socket


class _LocalWindow:
    """The in-process sliding window, used only while Redis is unreachable."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()
        self._last_sweep = 0.0

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits.setdefault(key, deque())
        cutoff = now - self.window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        return hits

    def _sweep(self, now: float) -> None:
        """Drop keys whose window has emptied.

        Keys come from caller-supplied email addresses, so without this a long
        run of attempts against invented addresses grows the dict without bound.
        """
        if now - self._last_sweep < self.window:
            return
        self._last_sweep = now
        cutoff = now - self.window
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= cutoff]:
            del self._hits[key]

    def retry_after(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            hits = self._prune(key, now)
            if len(hits) < self.limit:
                return 0
            return max(1, int(hits[0] + self.window - now) + 1)

    def record(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._sweep(now)
            self._prune(key, now).append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._last_sweep = 0.0


class Throttle:
    """Counts hits per key over a sliding window and refuses past ``limit``.

    Each key is a Redis sorted set of hit times that expires one window after
    its last hit, which is also what stops caller-supplied keys accumulating.
    """

    def __init__(self, name: str, *, limit: int, window_seconds: int) -> None:
        self.name = name
        self.limit = limit
        self.window = window_seconds
        self._local = _LocalWindow(limit, window_seconds)

    def _key(self, key: str) -> str:
        return f"{KEY_PREFIX}:{self.name}:{key}"

    def retry_after(self, key: str) -> int:
        """Seconds until ``key`` is allowed again, or 0 if it is allowed now."""
        return _shared(
            lambda r: int(r.retry_after(keys=[self._key(key)], args=[self.window, self.limit])),
            lambda: self._local.retry_after(key),
        )

    def record(self, key: str) -> None:
        _shared(
            lambda r: r.record(keys=[self._key(key)], args=[self.window, uuid.uuid4().hex]),
            lambda: self._local.record(key),
        )

    def clear(self, key: str) -> None:
        self._local.clear(key)
        _shared(lambda r: r.client.delete(self._key(key)), lambda: None)

    def reset(self) -> None:
        """Forget every key. For tests — see tests/integration/conftest.py."""
        self._local.reset()

        def delete_all(r: _Redis) -> None:
            keys = list(r.client.scan_iter(match=f"{KEY_PREFIX}:{self.name}:*", count=500))
            if keys:
                r.client.delete(*keys)

        _shared(delete_all, lambda: None)


# Failed password attempts. Counted per address so guessing one account's
# password is bounded wherever it is driven from, and per source address so a
# spray across many accounts is bounded too. Only failures are counted: a member
# signing in from several devices is not an attack.
LOGIN_BY_EMAIL = Throttle("login-email", limit=5, window_seconds=900)
LOGIN_BY_IP = Throttle("login-ip", limit=20, window_seconds=900)

# Password reset and verification resend share one budget. Both send mail to an
# address chosen by an anonymous caller, so the abuse — mailbox flooding, or
# burning a member's reset tokens — is the same whichever one is used.
EMAIL_DISPATCH_BY_EMAIL = Throttle("email-dispatch-email", limit=3, window_seconds=3600)
EMAIL_DISPATCH_BY_IP = Throttle("email-dispatch-ip", limit=10, window_seconds=3600)

# Registration creates a Person, a User and a Member row per call. The only
# limit read from settings: the dev stack raises it for the e2e suite (#462).
REGISTER_BY_IP = Throttle(
    "register-ip", limit=settings.REGISTER_LIMIT_PER_IP, window_seconds=3600
)

# Registering an address that already has an account mails its owner (#102), so
# the endpoint sends to an address an anonymous caller chose and needs the same
# per-address bound the reset and resend pair has. It does not share their
# budget: registration is not account recovery, and letting signup attempts
# spend a member's recovery allowance would turn a disclosure fix into a denial
# of service on their password reset. Enforced and recorded on every call, never
# only on the branch that sends — "did this attempt do anything" is the
# distinction the whole change exists to remove.
REGISTER_BY_EMAIL = Throttle("register-email", limit=3, window_seconds=3600)

ALL_THROTTLES = (
    LOGIN_BY_EMAIL,
    LOGIN_BY_IP,
    EMAIL_DISPATCH_BY_EMAIL,
    EMAIL_DISPATCH_BY_IP,
    REGISTER_BY_IP,
    REGISTER_BY_EMAIL,
)


def reset_all() -> None:
    for throttle in ALL_THROTTLES:
        throttle.reset()


def enforce(*pairs: tuple[Throttle, str]) -> None:
    """Raise 429 if any ``(throttle, key)`` is over its limit.

    Checks every pair before raising so the ``Retry-After`` reported is the
    longest wait of them all, rather than whichever happened to be listed first.
    """
    wait = max((throttle.retry_after(key) for throttle, key in pairs), default=0)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )


def record(*pairs: tuple[Throttle, str]) -> None:
    for throttle, key in pairs:
        throttle.record(key)


def identity_key(email: str) -> str:
    """Normalised bucket for an address, so casing cannot split the count."""
    return (email or "").strip().lower()
