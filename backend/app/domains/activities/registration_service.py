"""Registration service — business logic for activity registrations."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

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

    # 6. Check capacity
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

    return registration


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


def _determine_registration_status(
    activity: Activity,
    modality: ActivityModality | None,
    waiting_list_enabled: bool,
) -> str:
    """Determine whether a new registration should be confirmed or waitlisted."""
    # Check modality-level capacity first
    if modality and modality.max_participants is not None:
        if (modality.current_participants or 0) >= modality.max_participants:
            if waiting_list_enabled:
                return "waitlist"
            raise RegistrationError("This modality is full")

    # Check activity-level capacity
    if (activity.current_participants or 0) >= activity.max_participants:
        if waiting_list_enabled:
            return "waitlist"
        raise RegistrationError("Activity is full")

    return "confirmed"


def _promote_from_waitlist(
    db: Session, activity: Activity, modality_id: int | None = None
) -> Registration | None:
    """Promote the oldest waitlisted registration to confirmed."""
    query = (
        db.query(Registration)
        .filter(
            Registration.activity_id == activity.id,
            Registration.status == "waitlist",
        )
        .order_by(Registration.created_at.asc())
    )
    if modality_id:
        query = query.filter(Registration.modality_id == modality_id)

    next_in_line = query.first()
    if not next_in_line:
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

    return next_in_line
