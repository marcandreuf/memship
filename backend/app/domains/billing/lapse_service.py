"""Lapsed membership — reverting an unpaid member to the free tier, and back.

A member who stops paying used to keep their paid ``membership_type_id`` for
ever and keep walking into member-only activities. This module closes that: once
a membership fee has been unpaid for its due window plus a grace period, the
member is moved to the free default tier, and paying the outstanding fee moves
them back.

**Lapse is derived from dates, not from status.** A receipt only becomes
``overdue`` inside ``run_scheduled_reminders``, which returns early unless
``payment_reminders_enabled`` is set — a key with no default, so falsy on a
fresh install. A reversion anchored on the ``overdue`` status would therefore
never fire on a club that has not switched dunning on, which is precisely the
hole this exists to close, reintroduced through another feature's flag. Anchoring
on ``due_date`` — or ``return_date``, for a SEPA bounce that comes back days
later — behaves the same either way and needs no new stored state.

**The unpaid receipt is left standing.** The member held the paid tier for the
whole due-and-grace window and had its access throughout, so the fee was earned.
Voiding it would make non-payment a free way to use a paid tier for a month,
every period. The club pursues or writes it off with the tools it already has.

**Registrations already held are honoured.** ``check_eligibility`` runs only at
registration time, so a booking made while the member was paid up stays valid.
Cancelling it would be net-new work whose only effect is taking something away.

Reversion does not touch ``Member.status`` (see #145): a lapsed member is a full
member on the free tier, not a suspended one. The previous tier is parked on
``Member.membership_reverted_from_id`` because overwriting ``membership_type_id``
is what destroys it, and it is what makes paying restore the right plan.
"""

import logging
from datetime import date, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.domains.audit.models import AuditLog
from app.domains.billing.models import Receipt
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings

logger = logging.getLogger(__name__)

# Days after a membership fee falls due (or is returned by the bank) before the
# member loses the tier it pays for. Overridable with the
# ``membership_lapse_grace_days`` feature key.
#
# Twenty-one days sits on top of the 7-day membership fee window, so a member
# reverts about 28 days after the fee was emitted. The default dunning cadence
# (first reminder 3 days after due, then every 7, at most 3) puts the chases at
# days 10, 17 and 24 — all three go out before anyone loses access.
DEFAULT_GRACE_DAYS = 21

# Receipt statuses in which a membership fee is still owed and can lapse a
# member. ``pending`` is excluded: it has not been issued, so nobody has been
# asked for the money yet. ``paid`` is settled and ``cancelled`` is gone.
LAPSABLE_STATUSES = ("emitted", "overdue", "returned")


def lapse_enabled(db: Session) -> bool:
    """Whether this club reverts members whose membership fee goes unpaid.

    Off unless switched on. An upgrade must not start downgrading members on the
    night it lands — the club chooses when access starts depending on payment,
    and the settings screen warns that with dunning off the member's first
    notice is losing access.
    """
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    features = (org.features if org else None) or {}
    return bool(features.get("membership_lapse_enabled"))


def lapse_grace_days(db: Session) -> int:
    """Days past due (or past return) before an unpaid member loses their tier."""
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    features = (org.features if org else None) or {}
    try:
        return max(
            0, int(features.get("membership_lapse_grace_days", DEFAULT_GRACE_DAYS))
        )
    except (TypeError, ValueError):
        return DEFAULT_GRACE_DAYS


def default_membership_type(db: Session) -> MembershipType | None:
    """The free tier a lapsed member falls back to.

    ``is_default`` is unique among active rows and constrained to a zero price,
    so this is the one tier a member can hold without owing anything.
    """
    return (
        db.query(MembershipType)
        .filter(MembershipType.is_default.is_(True), MembershipType.is_active.is_(True))
        .first()
    )


def lapsed_receipts(db: Session, today: date | None = None) -> list[Receipt]:
    """Membership fees unpaid long enough that the member should lose their tier.

    Purchase receipts are excluded — they carry ``purchased_membership_type_id``
    and are voided at their due date by ``expire_unpaid_purchases``, because an
    abandoned checkout granted nothing there is anything to take away.

    A returned receipt lapses from its ``return_date``: a SEPA bounce arrives
    days after the due date through ``import-returns``, and counting the grace
    from the due date would eat most of it before anyone knew the money had
    failed.
    """
    today = today or date.today()
    cutoff = today - timedelta(days=lapse_grace_days(db))
    return (
        db.query(Receipt)
        .filter(
            Receipt.origin == "membership",
            Receipt.document_type == "invoice",
            Receipt.purchased_membership_type_id.is_(None),
            Receipt.is_active.is_(True),
            Receipt.status.in_(LAPSABLE_STATUSES),
            Receipt.payment_date.is_(None),
            or_(
                Receipt.due_date < cutoff,
                Receipt.return_date < cutoff,
            ),
        )
        .all()
    )


def _record(
    db: Session,
    member: Member,
    *,
    old_type_id: int | None,
    new_type_id: int | None,
    reason: str,
    receipt: Receipt,
) -> None:
    """Log a tier change to the audit trail so an admin can see why and when.

    ``user_id`` is left null: nobody pressed a button. The reason and the receipt
    number are what makes the row answer "why is this member on the free tier",
    which the tier id alone does not.
    """
    db.add(
        AuditLog(
            table_name="members",
            record_id=member.id,
            action="update",
            old_values={"membership_type_id": old_type_id},
            new_values={
                "membership_type_id": new_type_id,
                "reason": reason,
                "receipt_number": receipt.receipt_number,
                "receipt_id": receipt.id,
            },
            changed_fields=["membership_type_id"],
        )
    )


def revert_lapsed_members(db: Session, today: date | None = None) -> dict:
    """Move members with a long-unpaid membership fee onto the free tier.

    Idempotent: a member already on the default tier is skipped, so re-running
    the task changes nothing and a member who lapses, pays and lapses again is
    handled by the same two paths each time.

    Returns a small summary. Does not commit — the caller owns the transaction.
    """
    today = today or date.today()
    if not lapse_enabled(db):
        return {"lapsed": 0, "skipped": 0}

    free_tier = default_membership_type(db)
    if free_tier is None:
        # Without a free tier there is nowhere to revert to. Clearing the tier
        # instead would leave the member on no plan at all, which no other part
        # of the app produces, so nothing happens and the club is told.
        logger.error(
            "Membership lapse reversion skipped: no active default membership type"
        )
        return {"lapsed": 0, "skipped": 0}

    lapsed = 0
    skipped = 0
    seen: set[int] = set()
    for receipt in lapsed_receipts(db, today):
        if receipt.member_id in seen:
            continue
        seen.add(receipt.member_id)

        member = db.query(Member).filter(Member.id == receipt.member_id).first()
        if member is None or member.membership_type_id == free_tier.id:
            skipped += 1
            continue

        previous_id = member.membership_type_id
        member.membership_type_id = free_tier.id
        member.membership_reverted_from_id = previous_id
        member.membership_reverted_at = func.now()
        _record(
            db,
            member,
            old_type_id=previous_id,
            new_type_id=free_tier.id,
            reason="membership_fee_unpaid",
            receipt=receipt,
        )
        lapsed += 1

    db.flush()
    return {"lapsed": lapsed, "skipped": skipped}


def restore_reverted_membership(db: Session, receipt: Receipt) -> bool:
    """Put a lapsed member back on their plan when they settle the fee.

    Called inline by ``mark_receipt_paid``, so the plan comes back whichever way
    the money arrived — cash handed to the treasurer, a bank transfer, a card, a
    reconciled SEPA remittance. Restoring it in the card webhook alone would
    make paying in cash quietly worse than paying online.

    A no-op for every receipt that is not a membership fee, and for a member who
    has since moved on: if they are no longer on the free tier they have bought
    something in the meantime, and that newer plan is the one they should keep.

    Returns whether a tier was restored.
    """
    if receipt.origin != "membership":
        return False

    member = db.query(Member).filter(Member.id == receipt.member_id).first()
    if member is None or member.membership_reverted_from_id is None:
        return False

    previous_id = member.membership_reverted_from_id
    free_tier = default_membership_type(db)
    if free_tier is not None and member.membership_type_id != free_tier.id:
        # Moved on under their own steam — leave the tier alone, but stop
        # carrying a reversion that no longer describes anything.
        member.membership_reverted_from_id = None
        member.membership_reverted_at = None
        db.flush()
        return False

    restored_to = (
        db.query(MembershipType).filter(MembershipType.id == previous_id).first()
    )
    member.membership_reverted_from_id = None
    member.membership_reverted_at = None
    if restored_to is None:
        # The plan was deleted while the member was lapsed — ``ON DELETE SET
        # NULL`` has already emptied the column. There is nothing to restore and
        # the member stays where they are.
        db.flush()
        return False

    old_type_id = member.membership_type_id
    member.membership_type_id = restored_to.id
    _record(
        db,
        member,
        old_type_id=old_type_id,
        new_type_id=restored_to.id,
        reason="membership_fee_paid",
        receipt=receipt,
    )
    db.flush()
    return True
