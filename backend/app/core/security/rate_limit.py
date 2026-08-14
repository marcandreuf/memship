"""Sliding-window throttles for the unauthenticated auth endpoints.

`POST /auth/login` accepted unlimited attempts, and `User.is_locked` — read in
three places — was written by no code path at all, so nothing anywhere slowed a
password guess down. The same held for the two endpoints that send mail to an
arbitrary address on an anonymous request.

**Counters live in this process, not in Redis or the database.** The deployment
runs exactly one API container (`docker-compose.yml`) and `start.py` calls
`uvicorn.run` without `workers=`, so one process sees every attempt and an
in-memory window is exact. It is also the version with no new dependency, no
migration and no I/O on the login path. The cost is that a restart forgets the
counters and a second API replica would each keep their own — so **if this ever
runs behind more than one API process, this module has to move to Redis**,
which the stack already runs for Celery. That is the only thing that changes;
the call sites stay as they are.

Deliberately *not* done: flipping `users.is_locked` after N failures. That
column is the administrator's own switch, with `locked_reason` next to it, and
writing it from failed logins hands any anonymous caller a way to lock a named
member out permanently by guessing at their address. A window that expires on
its own bounds the same guessing without the denial-of-service.
"""

import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, Request, status


def client_ip(request: Request) -> str:
    """The caller's address, as far as it can be trusted.

    Every documented deployment puts Caddy in front of the API, so
    `request.client.host` is Caddy's address on the compose network and is the
    same for all callers — useless as a key. Caddy *appends* the peer it saw to
    `X-Forwarded-For`, so with one proxy in the chain the **rightmost** entry is
    the address Caddy actually accepted the connection from. Anything a client
    sends itself lands to the left of it and is ignored here.

    Publishing the API directly, with no proxy, makes the whole header
    caller-controlled and the per-IP limit evadable. The per-identity limits do
    not depend on it.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


class Throttle:
    """Counts hits per key over a sliding window and refuses past ``limit``."""

    def __init__(self, name: str, *, limit: int, window_seconds: int) -> None:
        self.name = name
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
        """Seconds until ``key`` is allowed again, or 0 if it is allowed now."""
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
        """Forget every key. For tests — see tests/integration/conftest.py."""
        with self._lock:
            self._hits.clear()
            self._last_sweep = 0.0


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

# Registration creates a Person, a User and a Member row per call.
REGISTER_BY_IP = Throttle("register-ip", limit=5, window_seconds=3600)

ALL_THROTTLES = (
    LOGIN_BY_EMAIL,
    LOGIN_BY_IP,
    EMAIL_DISPATCH_BY_EMAIL,
    EMAIL_DISPATCH_BY_IP,
    REGISTER_BY_IP,
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
