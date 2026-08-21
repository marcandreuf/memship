"""Registration service — business logic for activity registrations."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Query, Session, joinedload

logger = logging.getLogger(__name__)

from app.domains.activities.discount_service import (
    DiscountError,
    apply_discount,
    increment_usage,
    validate_discount_code,
)
from app.domains.activities.eligibility import check_eligibility
from app.domains.activities.models import (
    Activity,
    ActivityConsent,
    ActivityModality,
    ActivityPrice,
    Registration,
    RegistrationConsent,
)
from app.domains.members.models import Member


class RegistrationError(Exception):
    """Raised when a registration operation fails."""
    pass


# --- Query builders ---


def _registrations_base_query(db: Session) -> Query:
    return db.query(Registration).options(
        joinedload(Registration.member).joinedload(Member.person),
        joinedload(Registration.activity),
        joinedload(Registration.modality),
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
    return query.order_by(Registration.created_at.desc())


def build_member_registrations_query(
    db: Session, member_id: int, *, status: str | None = None
) -> Query:
    """Registrations for one member, shared by the list and CSV export."""
    query = _registrations_base_query(db).filter(
        Registration.member_id == member_id
    )
    if status:
        query = query.filter(Registration.status == status)
    return query.order_by(Registration.created_at.desc())


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

    # 2. Validate price belongs to this activity
    price = (
        db.query(ActivityPrice)
        .filter(
            ActivityPrice.id == price_id,
            ActivityPrice.activity_id == activity.id,
            ActivityPrice.is_active.is_(True),
        )
        .first()
    )
    if not price:
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
            discount = validate_discount_code(db, activity.id, discount_code)
            discounted_amount = apply_discount(original_amount, discount)
        except DiscountError as e:
            raise RegistrationError(str(e))

    # 5. Validate consents
    _validate_consents(db, activity.id, consents or [])

    # 6. Check capacity, under a row lock so the decision and the increment in
    #    step 10 cannot interleave with another registration.
    _lock_capacity_rows(db, activity, modality)
    waiting_list_enabled = activity.features.get("waiting_list", False) if activity.features else False
    status = _determine_registration_status(activity, modality, waiting_list_enabled)

    # 7. Create registration
    registration = Registration(
        activity_id=activity.id,
        member_id=member.id,
        modality_id=modality_id,
        price_id=price_id,
        discount_code_id=discount.id if discount else None,
        status=status,
        original_amount=original_amount,
        discounted_amount=discounted_amount,
        registration_data=registration_data or {},
        member_notes=member_notes,
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
    if status == "confirmed":
        activity.current_participants = (activity.current_participants or 0) + 1
        if modality:
            modality.current_participants = (modality.current_participants or 0) + 1
        price.current_registrations = (price.current_registrations or 0) + 1
    elif status == "waitlist":
        activity.waitlist_count = (activity.waitlist_count or 0) + 1

    # 11. Auto-generate activity receipt for confirmed registrations with amount
    if status == "confirmed":
        ensure_registration_receipt(db, registration, activity)

    # Dispatch email notification (async via Celery)
    _dispatch_registration_email(registration, activity, member)

    return registration


def ensure_registration_receipt(
    db: Session, registration: Registration, activity: Activity
) -> None:
    """Bill a confirmed registration, once.

    Every path that confirms a registration goes through here — registering into
    a free seat, a waitlist promotion, and an admin flipping the status — because
    a confirmed place in a paid activity has to be invoiced whichever of them
    produced it.

    Idempotent: a registration that already has a live receipt keeps it, so a
    re-confirmation does not bill twice. Cancellation cancels the receipt
    (`cancel_registration`), and a cancelled one deliberately does not block a
    new one — re-confirming after a cancellation owes money again.

    Receipt generation never fails the registration; the error is logged instead,
    because the seat has already been given and rolling it back here would be
    worse than an invoice an admin has to raise by hand.
    """
    amount = registration.discounted_amount
    if amount is None or Decimal(str(amount)) <= 0:
        return

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
        return

    try:
        from app.domains.billing.service import generate_activity_receipt

        generate_activity_receipt(
            db=db,
            registration_id=registration.id,
            member_id=registration.member_id,
            activity_name=activity.name,
            amount=Decimal(str(amount)),
            tax_rate=activity.tax_rate,
        )
    except Exception as e:
        logger.error(
            "Failed to generate receipt for registration %s: %s", registration.id, e
        )


def cancel_registration(
    db: Session,
    registration: Registration,
    cancelled_by_id: int | None = None,
    reason: str | None = None,
) -> Registration:
    """Cancel a registration and promote from waitlist if applicable."""
    if registration.status == "cancelled":
        raise RegistrationError("Registration is already cancelled")
    if registration.status not in ("confirmed", "waitlist", "pending"):
        raise RegistrationError(f"Cannot cancel registration with status '{registration.status}'")

    was_confirmed = registration.status == "confirmed"
    was_waitlisted = registration.status == "waitlist"

    registration.status = "cancelled"
    registration.cancelled_at = datetime.now(timezone.utc)
    registration.cancelled_by = cancelled_by_id
    registration.cancelled_reason = reason

    # Update counters
    activity = registration.activity
    if was_confirmed:
        activity.current_participants = max(0, (activity.current_participants or 0) - 1)
        if registration.modality:
            registration.modality.current_participants = max(
                0, (registration.modality.current_participants or 0) - 1
            )
        if registration.price:
            registration.price.current_registrations = max(
                0, (registration.price.current_registrations or 0) - 1
            )
    elif was_waitlisted:
        activity.waitlist_count = max(0, (activity.waitlist_count or 0) - 1)

    # Promote from waitlist if a confirmed spot freed up
    if was_confirmed:
        _promote_from_waitlist(db, activity, registration.modality_id)

    # Cancel unpaid receipts linked to this registration
    try:
        from app.domains.billing.models import Receipt
        unpaid_receipts = (
            db.query(Receipt)
            .filter(
                Receipt.registration_id == registration.id,
                Receipt.is_active.is_(True),
                Receipt.status.in_(["new", "pending", "emitted", "overdue"]),
            )
            .all()
        )
        for receipt in unpaid_receipts:
            receipt.status = "cancelled"
    except Exception:
        # The seat is already released, so failing the cancellation here would be
        # worse than an invoice left open — but it must not be invisible. A
        # receipt still standing against a cancelled registration is money the
        # member is asked for and does not owe, and nothing else reconciles the
        # two. Same reasoning as ensure_registration_receipt, which logs for the
        # mirror case.
        logger.exception(
            "Failed to cancel receipts for registration %s; a receipt may still "
            "stand against a cancelled registration",
            registration.id,
        )

    # Dispatch cancellation email (async via Celery)
    _dispatch_cancellation_email(registration, activity)

    return registration


def check_self_cancellation_allowed(
    activity: Activity, registration: Registration
) -> str | None:
    """Check if a member can self-cancel. Returns error message or None if allowed."""
    if not activity.allow_self_cancellation:
        return "Self-cancellation is not allowed for this activity"

    if registration.status not in ("confirmed", "waitlist"):
        return "Only confirmed or waitlisted registrations can be cancelled"

    if activity.self_cancellation_deadline_hours is not None:
        now = datetime.now(timezone.utc)
        deadline = activity.starts_at - timedelta(hours=activity.self_cancellation_deadline_hours)
        if now > deadline:
            return f"Cancellation deadline has passed ({activity.self_cancellation_deadline_hours}h before start)"

    return None


def admin_change_status(
    db: Session,
    registration: Registration,
    new_status: str,
    admin_notes: str | None = None,
) -> Registration:
    """Admin changes registration status."""
    old_status = registration.status
    if old_status == new_status:
        raise RegistrationError(f"Registration is already '{new_status}'")

    activity = registration.activity

    # Handle counter changes
    if old_status == "confirmed" and new_status != "confirmed":
        activity.current_participants = max(0, (activity.current_participants or 0) - 1)
        if registration.modality:
            registration.modality.current_participants = max(
                0, (registration.modality.current_participants or 0) - 1
            )
        if registration.price:
            registration.price.current_registrations = max(
                0, (registration.price.current_registrations or 0) - 1
            )
    if old_status == "waitlist" and new_status != "waitlist":
        activity.waitlist_count = max(0, (activity.waitlist_count or 0) - 1)

    if new_status == "confirmed" and old_status != "confirmed":
        activity.current_participants = (activity.current_participants or 0) + 1
        if registration.modality:
            registration.modality.current_participants = (registration.modality.current_participants or 0) + 1
        if registration.price:
            registration.price.current_registrations = (registration.price.current_registrations or 0) + 1
    if new_status == "waitlist" and old_status != "waitlist":
        activity.waitlist_count = (activity.waitlist_count or 0) + 1

    if new_status == "cancelled":
        registration.cancelled_at = datetime.now(timezone.utc)

    registration.status = new_status
    if new_status == "confirmed" and old_status != "confirmed":
        ensure_registration_receipt(db, registration, activity)
    if admin_notes:
        registration.admin_notes = admin_notes

    # If we freed a confirmed spot, promote from waitlist
    if old_status == "confirmed" and new_status != "confirmed":
        _promote_from_waitlist(db, activity, registration.modality_id)

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
    """Which capacity level is full, or None if a confirmed seat fits.

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
    """Whether one more confirmed seat fits, at both levels."""
    return _full_level(activity, modality) is None


def _determine_registration_status(
    activity: Activity,
    modality: ActivityModality | None,
    waiting_list_enabled: bool,
) -> str:
    """Determine whether a new registration should be confirmed or waitlisted."""
    full = _full_level(activity, modality)
    if full is None:
        return "confirmed"
    if waiting_list_enabled:
        return "waitlist"
    raise RegistrationError(
        "This modality is full" if full == "modality" else "Activity is full"
    )


def _promote_from_waitlist(
    db: Session, activity: Activity, modality_id: int | None = None
) -> Registration | None:
    """Promote the oldest waitlisted registration to confirmed.

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
        .order_by(Registration.created_at.asc())
    )

    next_in_line = query.first()
    if not next_in_line:
        return None

    if not _has_capacity(activity, next_in_line.modality):
        return None

    next_in_line.status = "confirmed"
    activity.current_participants = (activity.current_participants or 0) + 1
    activity.waitlist_count = max(0, (activity.waitlist_count or 0) - 1)

    if next_in_line.modality:
        next_in_line.modality.current_participants = (
            next_in_line.modality.current_participants or 0
        ) + 1
    if next_in_line.price:
        next_in_line.price.current_registrations = (
            next_in_line.price.current_registrations or 0
        ) + 1

    ensure_registration_receipt(db, next_in_line, activity)

    # Dispatch promotion email (async via Celery)
    _dispatch_promotion_email(next_in_line, activity)

    return next_in_line


# --- Email dispatch helpers ---

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
    registration: Registration, activity: Activity, member: "Member"
) -> None:
    """Dispatch registration confirmation email via Celery."""
    try:
        from app.tasks.email_tasks import send_registration_email_task
        email = _get_member_email(registration) or (member.person.email if member.person else None)
        if not email:
            return
        name = _get_member_name(registration) or (member.person.first_name if member.person else "")
        send_registration_email_task.delay(
            to=email,
            member_name=name,
            activity_name=activity.name,
            status=registration.status,
            activity_date=activity.starts_at.strftime("%d/%m/%Y") if activity.starts_at else None,
            location=activity.location,
        )
    except Exception as e:
        logger.error(f"Failed to dispatch registration email: {e}")


def _dispatch_cancellation_email(registration: Registration, activity: Activity) -> None:
    """Dispatch cancellation email via Celery."""
    try:
        from app.tasks.email_tasks import send_cancellation_email_task
        email = _get_member_email(registration)
        if not email:
            return
        send_cancellation_email_task.delay(
            to=email,
            member_name=_get_member_name(registration),
            activity_name=activity.name,
        )
    except Exception as e:
        logger.error(f"Failed to dispatch cancellation email: {e}")


def _dispatch_promotion_email(registration: Registration, activity: Activity) -> None:
    """Dispatch waitlist promotion email via Celery."""
    try:
        from app.tasks.email_tasks import send_promotion_email_task
        email = _get_member_email(registration)
        if not email:
            return
        send_promotion_email_task.delay(
            to=email,
            member_name=_get_member_name(registration),
            activity_name=activity.name,
            activity_date=activity.starts_at.strftime("%d/%m/%Y") if activity.starts_at else None,
            location=activity.location,
        )
    except Exception as e:
        logger.error(f"Failed to dispatch promotion email: {e}")
