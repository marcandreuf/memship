"""Activity service layer."""

import re
from unicodedata import normalize

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization import user_has
from app.domains.activities.models import Activity
from app.domains.activities.payment import auto_cancel_hours, needs_payment, unusable_methods
from app.domains.activities.registration_service import start_pending_deadlines
from app.domains.activities.schemas import ActivityCreate, ActivityUpdate
from app.domains.billing.seats import SeatError, refuse_auto_cancel_without_notices


def generate_slug(db: Session, name: str) -> str:
    """Generate a unique slug from an activity name."""
    # Transliterate accented characters
    slug = normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    # Lowercase and replace non-alphanumeric with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower())
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    # Remove consecutive hyphens
    slug = re.sub(r"-{2,}", "-", slug)

    if not slug:
        slug = "activity"

    # Check uniqueness
    base_slug = slug
    counter = 2
    while db.query(Activity).filter(Activity.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def get_visible_activity_or_404(db: Session, activity_id: int, user) -> Activity:
    """The activity, if this user may see it. Without ``activities.read`` only a
    published activity exists; a draft, archived or cancelled one is a 404, and
    so is everything hanging off it — prices, consents, modalities — or a
    member could read what the club has not published by walking the IDs."""
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity or (
        activity.status != "published" and not user_has(user, "activities.read")
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found"
        )
    return activity


def _refuse_auto_cancel_without_notices(db: Session) -> None:
    try:
        refuse_auto_cancel_without_notices(db)
    except SeatError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.detail)


def create_activity(db: Session, data: ActivityCreate, created_by_id: int) -> Activity:
    """Create a new activity."""
    # Validate dates
    if data.ends_at <= data.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ends_at must be after starts_at",
        )
    if data.registration_ends_at <= data.registration_starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="registration_ends_at must be after registration_starts_at",
        )
    if data.registration_ends_at > data.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="registration_ends_at must be before or equal to starts_at",
        )
    # Validate participants
    if data.max_participants < data.min_participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_participants must be >= min_participants",
        )

    if data.auto_cancel_enabled is True:
        _refuse_auto_cancel_without_notices(db)

    slug = generate_slug(db, data.name)

    activity = Activity(
        **data.model_dump(),
        slug=slug,
        created_by=created_by_id,
    )
    db.add(activity)
    db.flush()
    return activity


def update_activity(db: Session, activity: Activity, data: ActivityUpdate) -> Activity:
    """Update an existing activity."""
    update_data = data.model_dump(exclude_unset=True)

    if update_data.get("auto_cancel_enabled") is True and activity.auto_cancel_enabled is not True:
        _refuse_auto_cancel_without_notices(db)

    auto_cancel_was_on = auto_cancel_hours(db, activity) is not None
    for key, value in update_data.items():
        setattr(activity, key, value)
    if not auto_cancel_was_on:
        start_pending_deadlines(db, activity)

    # Validate dates after update
    if activity.ends_at <= activity.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ends_at must be after starts_at",
        )
    if activity.registration_ends_at <= activity.registration_starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="registration_ends_at must be after registration_starts_at",
        )
    if activity.registration_ends_at > activity.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="registration_ends_at must be before or equal to starts_at",
        )

    db.flush()
    return activity


def publish_activity(db: Session, activity: Activity) -> Activity:
    """Publish a draft activity."""
    if activity.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft activities can be published",
        )

    # Must have at least 1 price
    if not activity.prices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activity must have at least one price to be published",
        )

    # A seat that needs payment must have a way to be paid.
    if any(needs_payment(activity, p.amount) for p in activity.prices if p.is_active is not False):
        if not activity.payment_methods:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "payment_methods_required",
                    "message": "A paid activity must accept at least one payment method to be published",
                },
            )
        unusable = unusable_methods(db, activity.payment_methods)
        if unusable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "payment_methods_unavailable",
                    "methods": unusable,
                    "message": f"Payment methods not available at this club: {', '.join(unusable)}",
                },
            )

    # Must have required fields
    required = ["name", "starts_at", "ends_at", "registration_starts_at", "registration_ends_at", "max_participants"]
    for field in required:
        if getattr(activity, field) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Activity must have {field} set to be published",
            )

    activity.status = "published"
    db.flush()
    return activity


def archive_activity(db: Session, activity: Activity) -> Activity:
    """Archive a published or completed activity."""
    if activity.status not in ("published", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only published or completed activities can be archived",
        )

    activity.status = "archived"
    db.flush()
    return activity


def cancel_activity(db: Session, activity: Activity) -> Activity:
    """Cancel a draft or published activity."""
    if activity.status not in ("draft", "published"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft or published activities can be cancelled",
        )

    activity.status = "cancelled"
    db.flush()
    return activity
