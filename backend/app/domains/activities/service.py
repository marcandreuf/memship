"""Activity service layer."""

import re
from unicodedata import normalize

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domains.activities.models import Activity
from app.domains.activities.schemas import ActivityCreate, ActivityUpdate


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

    for key, value in update_data.items():
        setattr(activity, key, value)

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
