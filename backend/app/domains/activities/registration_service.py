"""Registration service — business logic for activity registrations."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Query, Session, joinedload, selectinload

from app.db.after_commit import run_after_commit

logger = logging.getLogger(__name__)

from app.domains.activities.discount_service import (
    DiscountError,
    apply_discount,
    increment_usage,
    release_usage,
    retake_usage,
    validate_discount_code,
)
from app.domains.activities.eligibility import check_eligibility
from app.domains.activities.payment import (
    auto_cancel_hours,
    needs_payment,
    payment_due_at,
    receipt_due_date,
    seat_payment_instructions,
)
from app.domains.shared.cancellation import is_late
from app.domains.activities.models import (
    Activity,
    ActivityConsent,
    ActivityModality,
    ActivityPrice,
    Registration,
    RegistrationConsent,
)
from app.domains.activities.pricing import member_can_hold_price
from app.domains.billing.payment_instructions import transfer_reference
from app.domains.members.models import Member
from app.domains.organizations.service import org_locale

# Statuses that hold a seat. A pending registration holds one while it waits to
# be paid, so every counter and every capacity decision reads this one rule.
OCCUPYING_STATUSES = ("confirmed", "pending")

# How long before its deadline a pending seat's holder is warned, at most. A
# shorter window is warned halfway through it instead.
DEADLINE_REMINDER_LEAD = timedelta(hours=24)


class RegistrationError(Exception):
    """Raised when a registration operation fails.

    ``detail`` is what the API answers: the English message, or with a
    ``code`` the ``{"code", ..., "message"}`` shape the UI translates.
    """

    def __init__(self, message: str, code: str | None = None, **fields):
        super().__init__(message)
        self.detail = {"code": code, **fields, "message": message} if code else message


def occupies_seat(status: str | None) -> bool:
    return status in OCCUPYING_STATUSES


def _move_counters(
    activity: Activity,
    modality: "ActivityModality | None",
    price: "ActivityPrice | None",
    old_status: str | None,
    new_status: str,
) -> None:
    """Keep the cached counters in step with one status change.

    Every path that changes a registration's status calls this, so the counters
    cannot drift from the rows by one path applying a different rule.
    """
    seat = occupies_seat(new_status) - occupies_seat(old_status)
    if seat:
        activity.current_participants = max(0, (activity.current_participants or 0) + seat)
        if modality:
            modality.current_participants = max(0, (modality.current_participants or 0) + seat)
        if price:
            price.current_registrations = max(0, (price.current_registrations or 0) + seat)
    waiting = (new_status == "waitlist") - (old_status == "waitlist")
    if waiting:
        activity.waitlist_count = max(0, (activity.waitlist_count or 0) + waiting)


# --- Query builders ---


def _registrations_base_query(db: Session) -> Query:
    return db.query(Registration).options(
        joinedload(Registration.member).joinedload(Member.person),
        joinedload(Registration.activity),
        joinedload(Registration.modality),
        selectinload(Registration.receipts),
    )


def build_activity_registrations_query(
    db: Session, activity_id: int, *, status: str | None = None
) -> Query:
    """Registrations for one activity, shared by the list and CSV export."""
    query = _registrations_base_query(db).filter(
        Registration.activity_id == activity_id
    )
    if status:
        query = query.filter(Registration.status == status)
    return query.order_by(Registration.created_at.desc(), Registration.id.desc())


def build_member_registrations_query(
    db: Session, party_id: int, *, status: str | None = None
) -> Query:
    """Registrations for one party, shared by the list and CSV export."""
    query = _registrations_base_query(db).filter(
        Registration.party_id == party_id
    )
    if status:
        query = query.filter(Registration.status == status)
    return query.order_by(Registration.created_at.desc(), Registration.id.desc())


def register_member(
    db: Session,
    activity: Activity,
    member: Member,
    price_id: int,
    modality_id: int | None = None,
    discount_code: str | None = None,
    consents: list | None = None,
    registration_data: dict | None = None,
    member_notes: str | None = None,
) -> Registration:
    """Register a member for an activity."""
    # 1. Check eligibility
    result = check_eligibility(db, activity, member)
    if not result.eligible:
        raise RegistrationError("; ".join(result.reasons))

    # 2. Validate the price belongs to this activity *and* that this member may
    #    hold it. The membership-type and visibility checks are deliberately
    #    here rather than only in what the member was offered: `price_id` comes
    #    straight from the request body, so a filter applied only on the way out
    #    is a suggestion (#427, #510).
    price = (
        db.query(ActivityPrice)
        .filter(
            ActivityPrice.id == price_id,
            ActivityPrice.activity_id == activity.id,
        )
        .first()
    )
    if not price or not member_can_hold_price(price, member):
        raise RegistrationError("Invalid price for this activity")

    # 3. Validate modality if provided
    modality = None
    if modality_id:
        modality = (
            db.query(ActivityModality)
            .filter(
                ActivityModality.id == modality_id,
                ActivityModality.activity_id == activity.id,
                ActivityModality.is_active.is_(True),
            )
            .first()
        )
        if not modality:
            raise RegistrationError("Invalid modality for this activity")

        # Check modality-specific deadline
        now = datetime.now(timezone.utc)
        if modality.registration_deadline and now > modality.registration_deadline:
            raise RegistrationError("Registration deadline for this modality has passed")

    # 4. Validate and apply discount code if provided
    discount = None
    original_amount = Decimal(str(price.amount))
    discounted_amount = original_amount
    if discount_code:
        try:
            # Locked: the cap check and the increment below are one decision.
            discount = validate_discount_code(
                db, activity.id, discount_code, for_update=True
            )
            discounted_amount = apply_discount(original_amount, discount)
        except DiscountError as e:
            raise RegistrationError(str(e))

    # 5. Validate consents
    _validate_consents(db, activity.id, consents or [])

    # 6. Check capacity, under a row lock so the decision and the increment in
    #    step 10 cannot interleave with another registration.
    _lock_capacity_rows(db, activity, modality)
    waiting_list_enabled = activity.features.get("waiting_list", False) if activity.features else False
    status = _determine_registration_status(
        activity, modality, waiting_list_enabled, discounted_amount
    )

    # 7. Create registration
    registration = Registration(
        activity_id=activity.id,
        party_id=member.party_id,
        modality_id=modality_id,
        price_id=price_id,
        discount_code_id=discount.id if discount else None,
        status=status,
        original_amount=original_amount,
        discounted_amount=discounted_amount,
        registration_data=registration_data or {},
        member_notes=member_notes,
        payment_due_at=(
            payment_due_at(db, activity, datetime.now(timezone.utc))
            if status == "pending"
            else None
        ),
    )
    db.add(registration)
    db.flush()

    # 8. Store consent acceptances
    for consent_input in (consents or []):
        rc = RegistrationConsent(
            registration_id=registration.id,
            activity_consent_id=consent_input.activity_consent_id,
            accepted=consent_input.accepted,
        )
        db.add(rc)

    # 9. Increment discount usage
    if discount:
        increment_usage(db, discount)

    # 10. Update cached counters
    _move_counters(activity, modality, price, None, status)
    # Written now: the next registration's capacity lock reloads the row with
    # populate_existing(), which would discard an unflushed increment.
    db.flush()

    # 11. Bill the seat: a confirmed one with an amount, or a pending one so the
    #     member can pay it.
    receipt = None
    if occupies_seat(status):
        receipt = ensure_registration_receipt(db, registration, activity)

    # Queued for after the endpoint commits — see _dispatch_registration_email.
    if status == "pending":
        _dispatch_pending_payment_email(db, registration, activity, member, receipt)
    else:
        _dispatch_registration_email(db, registration, activity, member)

    return registration


def ensure_registration_receipt(
    db: Session, registration: Registration, activity: Activity
):
    """Bill a seat, once, and return its live receipt (None for a free one).

    Every path that gives a registration a seat goes through here — registering
    into a free seat, a waitlist promotion, and an admin flipping the status —
    because a place in a paid activity has to be invoiced whichever of them
    produced it.

    A seat that needs payment (pay-to-confirm) gets a due date and a receipt no
    remittance collects, and the receipt is emailed once the caller commits,
    since paying it is what confirms the seat. A ``legacy`` activity's receipt is
    raised exactly as it always was.

    Idempotent: a registration that already has a live receipt keeps it, so a
    re-confirmation does not bill twice. Cancellation cancels the receipt
    (`cancel_registration`), and a cancelled one deliberately does not block a
    new one — re-confirming after a cancellation owes money again.

    For a ``legacy`` seat, receipt generation never fails the registration; the
    error is logged instead, because the seat has already been given and rolling
    it back here would be worse than an invoice an admin has to raise by hand. A
    seat that needs payment is the opposite: with no receipt it cannot be paid,
    so it would hold a place nobody can confirm. That raises, and the caller's
    transaction rolls back (#603).
    """
    amount = registration.discounted_amount
    if amount is None or Decimal(str(amount)) <= 0:
        return None

    from app.domains.billing.models import Receipt

    # The receipt a cancellation just voided may still be pending in the session
    # (the app's sessions do not autoflush), and it must not read as a live one.
    db.flush()
    existing = (
        db.query(Receipt)
        .filter(
            Receipt.registration_id == registration.id,
            Receipt.is_active.is_(True),
            Receipt.status != "cancelled",
        )
        .first()
    )
    if existing:
        return existing

    pay_to_confirm = needs_payment(activity, amount)
    try:
        from app.domains.billing.service import generate_activity_receipt

        # Receipt generation is best-effort: keep it in a SAVEPOINT so a failure
        # rolls back only the receipt, leaving the registration's transaction usable.
        with db.begin_nested():
            receipt = generate_activity_receipt(
                db=db,
                registration_id=registration.id,
                party_id=registration.party_id,
                activity_name=activity.name,
                amount=Decimal(str(amount)),
                tax_rate=activity.tax_rate,
                due_date=(
                    receipt_due_date(db, registration.payment_due_at)
                    if pay_to_confirm
                    else None
                ),
                is_batchable=not pay_to_confirm,
            )
    except Exception as e:
        if pay_to_confirm:
            logger.exception(
                "Failed to generate the receipt of pending registration %s",
                registration.id,
            )
            raise RegistrationError(
                "The receipt for this seat could not be raised, so it cannot be held",
                code="seat_receipt_failed",
            ) from e
        logger.error(
            "Failed to generate receipt for registration %s: %s", registration.id, e
        )
        return None

    if pay_to_confirm:
        _dispatch_receipt_email(db, receipt.id)
    return receipt


def confirm_pending_registration(db: Session, registration_id: int) -> None:
    """Confirm a registration whose receipt has just been paid.

    Only a ``pending`` one: a ``legacy`` activity never has any, and a seat
    already confirmed, waitlisted or cancelled is not this function's to change.
    """
    registration = (
        db.query(Registration).filter(Registration.id == registration_id).first()
    )
    if registration is None or registration.status != "pending":
        return
    registration.status = "confirmed"
    registration.payment_due_at = None
    _move_counters(
        registration.activity,
        registration.modality,
        registration.price,
        "pending",
        "confirmed",
    )
    db.flush()
    _dispatch_registration_email(
        db, registration, registration.activity, registration.member
    )


def cancel_registration(
    db: Session,
    registration: Registration,
    cancelled_by_id: int | None = None,
    reason: str | None = None,
    keep_payment: bool = False,
) -> Registration:
    """Cancel a registration and promote from waitlist if applicable."""
    if registration.status == "cancelled":
        raise RegistrationError("Registration is already cancelled")
    if registration.status not in ("confirmed", "waitlist", "pending"):
        raise RegistrationError(f"Cannot cancel registration with status '{registration.status}'")

    registration.cancelled_by = cancelled_by_id
    registration.cancelled_reason = reason
    _apply_status_change(db, registration, "cancelled", keep_payment=keep_payment)

    _dispatch_cancellation_email(db, registration, registration.activity)

    return registration


def _void_unpaid_receipts(db: Session, registration: Registration) -> None:
    """Cancel every receipt of this registration that still asks for money."""
    try:
        from app.domains.billing.models import Receipt
        from app.domains.billing.seats import void_unpaid_receipts

        void_unpaid_receipts(db, Receipt.registration_id, registration.id)
    except Exception:
        # The seat is already released, so failing the change here would be
        # worse than an invoice left open — but it must not be invisible. A
        # receipt still standing against a seat that no longer owes it is money
        # the member is asked for and does not owe, and nothing else reconciles
        # the two. Same reasoning as ensure_registration_receipt, which logs for
        # the mirror case.
        logger.exception(
            "Failed to cancel receipts for registration %s; a receipt may still "
            "stand against a registration that does not owe it",
            registration.id,
        )


def _apply_status_change(
    db: Session,
    registration: Registration,
    new_status: str,
    keep_payment: bool = False,
) -> str:
    """The one path every status change takes, and the receipt side of each.

    Counters, the discount use, the receipt and the waiting list move together
    here, so the member cancelling and the organiser changing the status cannot
    disagree about any of them. Paying a receipt is the only other way a seat
    changes (``confirm_pending_registration``), and it moves no counter.

    - to ``pending``: the seat gets its deadline and its receipt;
    - to ``confirmed``: the receipt is raised if it is not already there;
    - to ``waitlist`` or ``cancelled``: an unpaid receipt is cancelled, since
      a seat given back owes nothing. A paid one stays, and a cancelled seat
      that was paid for is owed back (``refund_status = due``) unless the
      organiser keeps the payment.

    Returns the status it changed from.
    """
    old_status = registration.status
    activity = registration.activity
    _move_counters(
        activity, registration.modality, registration.price, old_status, new_status
    )

    # The discount use follows the registration in and out of 'cancelled'.
    if registration.discount_code_id:
        if new_status == "cancelled":
            release_usage(db, registration.discount_code_id)
        elif old_status == "cancelled":
            retake_usage(db, registration.discount_code_id)

    registration.status = new_status
    if new_status == "cancelled":
        registration.cancelled_at = datetime.now(timezone.utc)
    else:
        # A seat that is live again is not cancelled: a late payment that gives
        # it back used to leave its cancellation date in the CSV (#591). What
        # happened stays in ``late_payment_at`` and the audit trail.
        registration.cancelled_at = None
        registration.cancelled_by = None
        registration.cancelled_reason = None
        registration.cancelled_cause = None
    registration.payment_reminder_sent_at = None
    registration.payment_due_at = (
        payment_due_at(db, activity, datetime.now(timezone.utc))
        if new_status == "pending"
        else None
    )

    if new_status in ("waitlist", "cancelled"):
        _void_unpaid_receipts(db, registration)
        if new_status == "cancelled" and _has_paid_receipt(db, registration):
            registration.refund_status = "none" if keep_payment else "due"
    elif occupies_seat(new_status):
        ensure_registration_receipt(db, registration, activity)

    if occupies_seat(old_status) and not occupies_seat(new_status):
        # A seat moved to the waiting list is not the one to promote into the
        # seat it just gave up.
        _promote_from_waitlist(
            db, activity, registration.modality_id, exclude_id=registration.id
        )

    return old_status


def _has_paid_receipt(db: Session, registration: Registration) -> bool:
    from app.domains.billing.models import Receipt

    db.flush()
    return (
        db.query(Receipt.id)
        .filter(
            Receipt.registration_id == registration.id,
            Receipt.is_active.is_(True),
            Receipt.status == "paid",
        )
        .first()
        is not None
    )


def settle_late_payment(db: Session, receipt):
    """Give a seat back to a payment that arrived after it was released.

    Confirmed if a seat is free, under the same capacity lock a registration
    takes; otherwise it stays cancelled and the money is owed back. Flagged for
    the organiser either way.
    """
    from app.domains.billing.seats import LateSeat

    registration = (
        db.query(Registration).filter(Registration.id == receipt.registration_id).one()
    )
    activity = registration.activity
    registration.late_payment_at = datetime.now(timezone.utc)
    registration.late_payment_seen_at = None

    confirmed = occupies_seat(registration.status)
    if not confirmed:
        _lock_capacity_rows(db, activity, registration.modality)
        if _has_capacity(activity, registration.modality):
            _apply_status_change(db, registration, "confirmed")
            registration.refund_status = "none"
            _dispatch_registration_email(db, registration, activity, registration.member)
            confirmed = True
        else:
            registration.refund_status = "due"
            _dispatch_late_payment_refund_email(db, registration, activity, receipt)
    db.flush()

    person = registration.member.person if registration.member else None
    return LateSeat(
        confirmed=confirmed,
        name=activity.name,
        member_name=f"{person.first_name} {person.last_name}" if person else None,
    )


def expired_pending_registrations(db: Session, now: datetime) -> list[Registration]:
    """Pending seats whose payment deadline has passed.

    Locked, skipping rows another transaction holds: a payment confirming the
    seat at this moment wins, and the next sweep sees it confirmed.
    """
    return (
        db.query(Registration)
        .filter(
            Registration.status == "pending",
            Registration.payment_due_at.isnot(None),
            Registration.payment_due_at < now,
        )
        .order_by(Registration.payment_due_at, Registration.id)
        .with_for_update(skip_locked=True, of=Registration)
        .all()
    )


def expire_unpaid_registration(db: Session, registration: Registration) -> None:
    """Cancel a seat left unpaid past its deadline, and tell the member.

    The one status path voids the receipt, releases the discount use and gives
    the seat to the next in line, who may in turn be pending.
    """
    registration.cancelled_cause = "payment_expired"
    _apply_status_change(db, registration, "cancelled")
    _dispatch_unpaid_cancellation_email(db, registration, registration.activity)


def start_pending_deadlines(
    db: Session, activity: Activity, now: datetime | None = None
) -> int:
    """Give the activity's pending seats a deadline when auto-cancel comes on.

    A seat taken while auto-cancel was off has no deadline, so switching it on
    later never touched it: it stayed pending for good (#591). Each such seat
    gets the full window from now, its receipt falls due by then, and its
    member is sent the pending mail again, now with the deadline — a seat must
    not be released before its holder has been told it can be. Returns how
    many seats were given a deadline. Does not commit.
    """
    hours = auto_cancel_hours(db, activity)
    if hours is None:
        return 0
    now = now or datetime.now(timezone.utc)
    due_at = now + timedelta(hours=hours)
    seats = (
        db.query(Registration)
        .filter(
            Registration.activity_id == activity.id,
            Registration.status == "pending",
            Registration.payment_due_at.is_(None),
        )
        .all()
    )
    for registration in seats:
        registration.payment_due_at = due_at
        registration.payment_reminder_sent_at = None
        receipt = registration.current_receipt
        if receipt is not None and receipt.status in ("emitted", "overdue"):
            due_date = receipt_due_date(db, due_at)
            if receipt.due_date is None or due_date < receipt.due_date:
                receipt.due_date = due_date
        _dispatch_pending_payment_email(
            db, registration, activity, registration.member, receipt, deadline_added=True
        )
    db.flush()
    return len(seats)


def _payment_window(db: Session, registration: Registration) -> timedelta:
    """How long the member was given to pay.

    The deadline is always set as "now + the activity's hours" — at
    registration, at a promotion from the waiting list, or when auto-cancel is
    switched on later — so the hours are the window. Measuring from
    ``created_at`` instead counted a promoted member's days on the waiting
    list, and warned them on the first hourly run after the promotion (#591).
    """
    hours = auto_cancel_hours(db, registration.activity)
    if hours is not None:
        return timedelta(hours=hours)
    return registration.payment_due_at - registration.created_at


def remind_pending_deadlines(db: Session, now: datetime | None = None) -> int:
    """Warn, once, each member whose pending seat is about to expire.

    Warned ``DEADLINE_REMINDER_LEAD`` before the deadline, or halfway through a
    window shorter than twice that, so the cancellation is never a surprise.
    Returns how many were warned. Does not commit.
    """
    now = now or datetime.now(timezone.utc)
    pending = (
        db.query(Registration)
        .filter(
            Registration.status == "pending",
            Registration.payment_due_at.isnot(None),
            Registration.payment_due_at > now,
            Registration.payment_reminder_sent_at.is_(None),
        )
        .all()
    )
    warned = 0
    for registration in pending:
        window = _payment_window(db, registration)
        lead = min(DEADLINE_REMINDER_LEAD, window / 2)
        if now < registration.payment_due_at - lead:
            continue
        receipt = registration.current_receipt
        if receipt is None:
            continue
        registration.payment_reminder_sent_at = now
        _dispatch_deadline_reminder_email(db, registration, registration.activity, receipt)
        warned += 1
    db.flush()
    return warned


def self_cancellation_policy(
    activity: Activity, registration: Registration
) -> tuple[str | None, bool]:
    """What the activity's policy says to a member cancelling their own seat (#604).

    Returns ``(error, keep_payment)``. ``error`` is why the cancellation is
    refused, or None. ``keep_payment`` is True when it is allowed past the
    refund deadline: the seat is released and the club keeps what was paid. A
    seat that was never paid has nothing to keep, so the flag then changes nothing.
    """
    if not activity.allow_self_cancellation:
        return "Self-cancellation is not allowed for this activity", False

    if registration.status not in ("confirmed", "waitlist", "pending"):
        return "Only confirmed, pending or waitlisted registrations can be cancelled", False

    if is_late(
        datetime.now(timezone.utc),
        activity.starts_at,
        activity.self_cancellation_deadline_minutes,
    ):
        if activity.late_cancellation_mode == "allow_no_refund":
            return None, True
        return (
            f"Cancellation deadline has passed ({activity.self_cancellation_deadline_minutes} minutes before start)",
            False,
        )

    return None, False


def admin_change_status(
    db: Session,
    registration: Registration,
    new_status: str,
    admin_notes: str | None = None,
    keep_payment: bool = False,
) -> Registration:
    """The organiser changes a registration's status.

    A seat that needs payment is confirmed by paying its receipt or, explicitly,
    by ``confirm_without_payment``; a status flip must not leave a confirmed
    attendee with a live receipt the dunning run would chase. For the same
    reason only such a seat can be put back to ``pending``.
    """
    if registration.status == new_status:
        raise RegistrationError(f"Registration is already '{new_status}'")

    owes = needs_payment(registration.activity, registration.discounted_amount)
    if new_status == "confirmed" and owes and not _has_paid_receipt(db, registration):
        raise RegistrationError(
            "This seat needs payment: mark its receipt paid or confirm it without payment",
            code="seat_needs_payment",
        )
    if new_status == "pending" and not owes:
        raise RegistrationError("Only a seat that needs payment can be pending")

    _apply_status_change(db, registration, new_status, keep_payment=keep_payment)
    if admin_notes:
        registration.admin_notes = admin_notes
    # The member hears about it as when they cancel themselves: the panel is
    # where the organiser now cancels, and a seat lost in silence is a surprise
    # at the door (#591).
    if new_status == "cancelled":
        _dispatch_cancellation_email(db, registration, registration.activity)

    return registration


def confirm_without_payment(
    db: Session, registration: Registration, user_id: int
) -> Registration:
    """Confirm a pending seat and waive its payment, on the organiser's word.

    The receipt is cancelled rather than left standing, so a confirmed attendee
    never carries a live receipt the dunning run would chase. Recorded in the
    audit log, since it gives up money the club was owed.
    """
    if registration.status != "pending":
        raise RegistrationError("Only a pending registration can be confirmed without payment")

    from app.domains.audit.models import AuditLog

    _void_unpaid_receipts(db, registration)
    registration.status = "confirmed"
    registration.payment_due_at = None
    db.add(
        AuditLog(
            table_name="registrations",
            record_id=registration.id,
            action="update",
            user_id=user_id,
            old_values={"status": "pending"},
            new_values={"status": "confirmed", "reason": "payment_waived"},
            changed_fields=["status"],
        )
    )
    db.flush()
    _dispatch_registration_email(
        db, registration, registration.activity, registration.member
    )
    return registration


def _validate_consents(db: Session, activity_id: int, consents: list) -> None:
    """Validate that all mandatory consents are accepted."""
    mandatory_consents = (
        db.query(ActivityConsent)
        .filter(
            ActivityConsent.activity_id == activity_id,
            ActivityConsent.is_mandatory.is_(True),
            ActivityConsent.is_active.is_(True),
        )
        .all()
    )
    if not mandatory_consents:
        return

    # Build a map of accepted consent IDs
    accepted_ids = {
        c.activity_consent_id for c in consents if c.accepted
    }

    missing = [c for c in mandatory_consents if c.id not in accepted_ids]
    if missing:
        names = ", ".join(c.title for c in missing)
        raise RegistrationError(f"Mandatory consents not accepted: {names}")


def _lock_capacity_rows(
    db: Session, activity: Activity, modality: "ActivityModality | None"
) -> None:
    """Serialize the read-modify-write on the capacity counters.

    ``current_participants`` is a cached column incremented in Python, so two
    registrations arriving together both read ``max - 1``, both take the
    confirmed branch and both increment: the activity ends up over capacity and
    the counter drifts from the ``registrations`` rows. Locking the row the
    decision reads makes the second caller wait for the first to commit.

    ``populate_existing()`` is not optional. The activity is already in the
    session — the endpoint loaded it to return a 404 — and without it SQLAlchemy
    hands back the identity-mapped instance with the *stale* counter still
    attached, so the lock would be taken and then the old value read straight
    through it.

    Rows are always locked activity-then-modality so two callers cannot take
    them in opposite orders and deadlock.

    This is the pattern ``domains/bookings/service.py`` already uses on
    ``space_slots``.
    """
    db.query(Activity).filter(Activity.id == activity.id).populate_existing().with_for_update().first()
    if modality is not None:
        (
            db.query(ActivityModality)
            .filter(ActivityModality.id == modality.id)
            .populate_existing()
            .with_for_update()
            .first()
        )


def _full_level(activity: Activity, modality: "ActivityModality | None") -> str | None:
    """Which capacity level is full, or None if one more seat fits.

    The single place the capacity rule lives. Both the new-registration path and
    waitlist promotion ask this, so the two cannot drift apart — promotion used
    to skip the check entirely. Modality is tested first because it is the
    narrower cap. ``Activity.max_participants`` is NOT NULL; a modality's is
    optional and means "no cap of its own".
    """
    if modality is not None and modality.max_participants is not None:
        if (modality.current_participants or 0) >= modality.max_participants:
            return "modality"
    if (activity.current_participants or 0) >= activity.max_participants:
        return "activity"
    return None


def _has_capacity(activity: Activity, modality: "ActivityModality | None") -> bool:
    """Whether one more seat fits, at both levels."""
    return _full_level(activity, modality) is None


def _determine_registration_status(
    activity: Activity,
    modality: ActivityModality | None,
    waiting_list_enabled: bool,
    amount: Decimal | None,
) -> str:
    """Decide a new registration's status: a seat, or the waiting list.

    A seat that needs payment is ``pending`` until its receipt is paid; any
    other seat is confirmed at once. ``needs_payment`` is false for a ``legacy``
    activity, which is what keeps that flow exactly as it was.
    """
    full = _full_level(activity, modality)
    if full is None:
        return "pending" if needs_payment(activity, amount) else "confirmed"
    if waiting_list_enabled:
        return "waitlist"
    if full == "modality":
        raise RegistrationError("This modality is full", code="modality_full")
    raise RegistrationError("Activity is full", code="activity_full")


def _promote_from_waitlist(
    db: Session,
    activity: Activity,
    modality_id: int | None = None,
    exclude_id: int | None = None,
) -> Registration | None:
    """Give the freed seat to the oldest waitlisted registration.

    It is ``pending`` when the seat needs payment, with its deadline and its
    receipt, and sent the pending-payment mail; ``confirmed`` otherwise, and
    sent ``waitlist_promoted``. Goes through the one status-change
    path, so if that pending seat later expires unpaid, cancelling it promotes
    the next in line in turn.

    Only ever fills the seat that was actually freed. ``modality_id`` is the
    modality of the cancelled registration, and a promotion must match it: with
    an unfiltered query, cancelling a registration that had no modality promoted
    the oldest waitlister in the whole activity — possibly one waiting on a
    different modality that is still full — and then incremented that modality
    past its own cap. ``None`` means the freed seat had no modality, so the
    candidates are the waitlisters that also have none.

    Capacity is re-checked rather than assumed. A freed seat is not proof there
    is room: an admin may have lowered the cap while people were waiting.
    """
    modality_filter = (
        Registration.modality_id == modality_id
        if modality_id is not None
        else Registration.modality_id.is_(None)
    )
    query = (
        db.query(Registration)
        .filter(
            Registration.activity_id == activity.id,
            Registration.status == "waitlist",
            modality_filter,
        )
        .order_by(Registration.created_at.asc(), Registration.id.asc())
    )
    if exclude_id is not None:
        query = query.filter(Registration.id != exclude_id)

    next_in_line = query.first()
    if not next_in_line:
        return None

    if not _has_capacity(activity, next_in_line.modality):
        return None

    new_status = (
        "pending"
        if needs_payment(activity, next_in_line.discounted_amount)
        else "confirmed"
    )
    _apply_status_change(db, next_in_line, new_status)
    receipt = ensure_registration_receipt(db, next_in_line, activity)

    if new_status == "pending":
        # The pending-payment mail, not waitlist_promoted: it is the one a club
        # cannot run a pay-to-confirm activity without (seeded on, and guarded),
        # so a member holding a seat they must pay for is always told so (#619).
        _dispatch_pending_payment_email(
            db, next_in_line, activity, next_in_line.member, receipt, promoted=True
        )
    else:
        _dispatch_promotion_email(db, next_in_line, activity)

    return next_in_line


# --- Email dispatch helpers ---
#
# Each helper resolves the email payload now, while the ORM objects are loaded,
# and queues the Celery ``.delay()`` on the session with ``run_after_commit``.
# Sending from inside the service was a race: the worker could read the
# database before the registration row was committed, and a commit that failed
# afterwards left the member told about a registration that never existed.
# The task takes the payload explicitly and never re-reads the row.

def _get_member_email(registration: Registration) -> str | None:
    """Get the member's email address from the registration."""
    try:
        return registration.member.person.email
    except (AttributeError, TypeError):
        return None


def _get_member_name(registration: Registration) -> str:
    """Get the member's first name from the registration."""
    try:
        return registration.member.person.first_name
    except (AttributeError, TypeError):
        return ""


def _dispatch_registration_email(
    db: Session, registration: Registration, activity: Activity, member: "Member"
) -> None:
    """Queue the registration confirmation email for after commit."""
    try:
        from app.tasks.email_tasks import send_registration_email_task
        email = _get_member_email(registration) or (member.person.email if member.person else None)
        if not email:
            return
        name = _get_member_name(registration) or (member.person.first_name if member.person else "")
        payload = dict(
            to=email,
            member_name=name,
            activity_name=activity.name,
            status=registration.status,
            activity_date=activity.starts_at.strftime("%d/%m/%Y") if activity.starts_at else None,
            location=activity.location,
            locale=org_locale(db),
        )
        # Told only on a confirmed paid seat that keeps its payment when cancelled
        # late: everything else needs no sentence (#638).
        if (
            registration.status == "confirmed"
            and activity.allow_self_cancellation
            and activity.late_cancellation_mode == "allow_no_refund"
            and activity.self_cancellation_deadline_minutes
            and registration.discounted_amount is not None
            and Decimal(str(registration.discounted_amount)) > 0
        ):
            payload["cancellation_deadline_minutes"] = activity.self_cancellation_deadline_minutes
            payload["late_cancellation_keeps_payment"] = True
        run_after_commit(db, lambda: send_registration_email_task.delay(**payload))
    except Exception as e:
        logger.error(f"Failed to dispatch registration email: {e}")


def _dispatch_late_payment_refund_email(
    db: Session, registration: Registration, activity: Activity, receipt
) -> None:
    """Queue the "paid too late, no seat, money goes back" email for after commit."""
    try:
        from app.domains.organizations.models import OrganizationSettings
        from app.tasks.email_tasks import send_late_payment_refund_email_task

        member = registration.member
        person = member.person if member else None
        email = _get_member_email(registration) or (person.email if person else None)
        if not email:
            return
        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        payload = dict(
            to=email,
            member_name=_get_member_name(registration) or (person.first_name if person else ""),
            activity_name=activity.name,
            amount=f"{receipt.total_amount:.2f}",
            currency=(org.currency if org else None) or "EUR",
            receipt_number=receipt.receipt_number,
            locale=org_locale(db),
        )
        run_after_commit(db, lambda: send_late_payment_refund_email_task.delay(**payload))
    except Exception as e:
        logger.error(f"Failed to dispatch late payment refund email: {e}")


def _dispatch_pending_payment_email(
    db: Session,
    registration: Registration,
    activity: Activity,
    member: "Member",
    receipt,
    deadline_added: bool = False,
    promoted: bool = False,
) -> None:
    """Queue the "your seat is held until you pay" email for after commit.

    ``deadline_added`` is the resend when auto-cancel starts on a seat that was
    already held: the member already had this mail, and is told what changed.
    ``promoted`` is a waitlister handed a freed seat.
    """
    try:
        from app.tasks.email_tasks import send_pending_payment_email_task

        email = _get_member_email(registration) or (member.person.email if member.person else None)
        if not email or receipt is None:
            return
        locale = org_locale(db)
        payload = dict(
            to=email,
            member_name=_get_member_name(registration) or (member.person.first_name if member.person else ""),
            activity_name=activity.name,
            locale=locale,
            deadline_added=deadline_added,
            promoted=promoted,
            **_seat_payment(db, registration, activity, receipt, locale),
        )
        run_after_commit(db, lambda: send_pending_payment_email_task.delay(**payload))
    except Exception as e:
        logger.error(f"Failed to dispatch pending-payment email: {e}")


def _seat_payment(
    db: Session, registration: Registration, activity: Activity, receipt, locale: str
) -> dict:
    """What a mail about a seat held until paid tells the member: the amount,
    the deadline and the ways this activity accepts."""
    from app.core.clock import org_timezone
    from app.domains.organizations.models import OrganizationSettings

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    instructions = seat_payment_instructions(db, activity, locale)
    return dict(
        amount=f"{receipt.total_amount:.2f}",
        currency=(org.currency if org else None) or "EUR",
        deadline=(
            registration.payment_due_at.astimezone(org_timezone(db)).strftime("%d/%m/%Y %H:%M")
            if registration.payment_due_at
            else None
        ),
        pay_now_url=instructions.pay_now_url,
        bank_details=instructions.bank_details,
        cash=instructions.cash,
        # Without a deadline the receipt's own due date is what the member has.
        due_date=(
            receipt.due_date.strftime("%d/%m/%Y")
            if receipt.due_date and not registration.payment_due_at
            else None
        ),
        # What to write on a transfer so the club can match it.
        reference=transfer_reference(receipt) if instructions.bank_details else None,
    )


def _dispatch_deadline_reminder_email(
    db: Session, registration: Registration, activity: Activity, receipt
) -> None:
    """Queue the "your seat expires soon" email for after commit."""
    try:
        from app.tasks.email_tasks import send_deadline_reminder_email_task

        email = _get_member_email(registration)
        if not email:
            return
        locale = org_locale(db)
        payload = dict(
            to=email,
            member_name=_get_member_name(registration),
            activity_name=activity.name,
            locale=locale,
            **_seat_payment(db, registration, activity, receipt, locale),
        )
        run_after_commit(db, lambda: send_deadline_reminder_email_task.delay(**payload))
    except Exception as e:
        logger.error(f"Failed to dispatch deadline reminder email: {e}")


def _dispatch_unpaid_cancellation_email(
    db: Session, registration: Registration, activity: Activity
) -> None:
    """Queue the "cancelled for non-payment" email for after commit."""
    try:
        from app.tasks.email_tasks import send_unpaid_cancellation_email_task

        email = _get_member_email(registration)
        if not email:
            return
        payload = dict(
            to=email,
            member_name=_get_member_name(registration),
            activity_name=activity.name,
            locale=org_locale(db),
        )
        run_after_commit(
            db, lambda: send_unpaid_cancellation_email_task.delay(**payload)
        )
    except Exception as e:
        logger.error(f"Failed to dispatch unpaid-cancellation email: {e}")


def _dispatch_receipt_email(db: Session, receipt_id: int) -> None:
    """Queue the receipt itself (PDF and how to pay) for after commit."""
    try:
        from app.tasks.email_tasks import send_receipt_email_task

        run_after_commit(db, lambda: send_receipt_email_task.delay(receipt_id))
    except Exception as e:
        logger.error(f"Failed to dispatch receipt email: {e}")


def _dispatch_cancellation_email(
    db: Session, registration: Registration, activity: Activity
) -> None:
    """Queue the cancellation email for after commit."""
    try:
        from app.tasks.email_tasks import send_cancellation_email_task
        email = _get_member_email(registration)
        if not email:
            return
        payload = dict(
            to=email,
            member_name=_get_member_name(registration),
            activity_name=activity.name,
            locale=org_locale(db),
            # A paid seat cancelled without keeping the payment owes it back.
            refund_due=registration.refund_status == "due",
        )
        run_after_commit(db, lambda: send_cancellation_email_task.delay(**payload))
    except Exception as e:
        logger.error(f"Failed to dispatch cancellation email: {e}")


def _dispatch_promotion_email(
    db: Session, registration: Registration, activity: Activity
) -> None:
    """Queue the "you're in" email for a promotion confirmed at once."""
    try:
        from app.tasks.email_tasks import send_promotion_email_task
        email = _get_member_email(registration)
        if not email:
            return
        payload = dict(
            to=email,
            member_name=_get_member_name(registration),
            activity_name=activity.name,
            activity_date=activity.starts_at.strftime("%d/%m/%Y") if activity.starts_at else None,
            location=activity.location,
            locale=org_locale(db),
        )
        run_after_commit(db, lambda: send_promotion_email_task.delay(**payload))
    except Exception as e:
        logger.error(f"Failed to dispatch promotion email: {e}")
