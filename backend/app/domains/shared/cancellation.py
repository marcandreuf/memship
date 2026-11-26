"""The cancellation policy of a paid seat, shared by activities and spaces (#604).

Both decide the same two things for a member who cancels: whether it is allowed,
and whether what they paid is owed back. They keep separate settings, so the
rule lives here and the deadline comes from each.
"""

from datetime import datetime, timedelta
from typing import Literal

#: ``block`` refuses a cancellation past the deadline; ``allow_no_refund``
#: releases the seat and the club keeps the payment.
LATE_CANCELLATION_MODES = ("block", "allow_no_refund")
LateCancellationMode = Literal["block", "allow_no_refund"]

#: A year. Keeps ``timedelta`` from overflowing on an absurd value.
MAX_CANCELLATION_MINUTES = 525_600


def cancellation_deadline(starts_at: datetime, deadline_minutes: int | None) -> datetime | None:
    """The last moment a member's cancellation is refundable, or None for no limit."""
    if deadline_minutes is None:
        return None
    return starts_at - timedelta(minutes=deadline_minutes)


def is_late(now: datetime, starts_at: datetime, deadline_minutes: int | None) -> bool:
    deadline = cancellation_deadline(starts_at, deadline_minutes)
    return deadline is not None and now >= deadline
