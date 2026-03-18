"""Activity endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.db_utils import get_or_404
from app.core.pagination import paginate
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.activities.models import Activity
from app.domains.activities.schemas import (
    ActivityCreate,
    ActivityListResponse,
    ActivityResponse,
    ActivityUpdate,
)
from app.domains.activities.service import (
    archive_activity,
    cancel_activity,
    create_activity,
    publish_activity,
    update_activity,
)
from app.domains.auth.models import User

router = APIRouter(prefix="/activities", tags=["activities"])


def _to_response(activity: Activity) -> ActivityResponse:
    now = datetime.now(timezone.utc)
    available_spots = max(0, activity.max_participants - (activity.current_participants or 0))
    is_registration_open = (
        activity.status == "published"
        and activity.registration_starts_at is not None
        and activity.registration_ends_at is not None
        and now >= activity.registration_starts_at
        and now <= activity.registration_ends_at
    )

    return ActivityResponse(
        id=activity.id,
        name=activity.name,
        slug=activity.slug,
        description=activity.description,
        short_description=activity.short_description,
        starts_at=activity.starts_at,
        ends_at=activity.ends_at,
        location=activity.location,
        location_details=activity.location_details,
        location_url=activity.location_url,
        registration_starts_at=activity.registration_starts_at,
        registration_ends_at=activity.registration_ends_at,
        min_participants=activity.min_participants or 0,
        max_participants=activity.max_participants,
        current_participants=activity.current_participants or 0,
        waitlist_count=activity.waitlist_count or 0,
        available_spots=available_spots,
        is_registration_open=is_registration_open,
        min_age=activity.min_age,
        max_age=activity.max_age,
        allowed_membership_types=activity.allowed_membership_types,
        status=activity.status,
        tax_rate=float(activity.tax_rate) if activity.tax_rate is not None else 0,
        image_url=activity.image_url,
        thumbnail_url=activity.thumbnail_url,
        features=activity.features or {},
        registration_fields_schema=activity.registration_fields_schema or [],
        requirements=activity.requirements,
        what_to_bring=activity.what_to_bring,
        cancellation_policy=activity.cancellation_policy,
        allow_self_cancellation=activity.allow_self_cancellation or False,
        self_cancellation_deadline_hours=activity.self_cancellation_deadline_hours,
        is_active=activity.is_active,
        is_featured=activity.is_featured or False,
        created_by=activity.created_by,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
        modalities=[m for m in activity.modalities] if activity.modalities else [],
        prices=[p for p in activity.prices] if activity.prices else [],
    )


def _to_list_response(activity: Activity) -> ActivityListResponse:
    now = datetime.now(timezone.utc)
    available_spots = max(0, activity.max_participants - (activity.current_participants or 0))
    is_registration_open = (
        activity.status == "published"
        and activity.registration_starts_at is not None
        and activity.registration_ends_at is not None
        and now >= activity.registration_starts_at
        and now <= activity.registration_ends_at
    )

    return ActivityListResponse(
        id=activity.id,
        name=activity.name,
        slug=activity.slug,
        short_description=activity.short_description,
        starts_at=activity.starts_at,
        ends_at=activity.ends_at,
        location=activity.location,
        max_participants=activity.max_participants,
        current_participants=activity.current_participants or 0,
        available_spots=available_spots,
        is_registration_open=is_registration_open,
        status=activity.status,
        is_featured=activity.is_featured or False,
        created_at=activity.created_at,
    )


@router.get("/")
def list_activities(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Activity).filter(Activity.is_active.is_(True))

    # Members can only see published activities
    if current_user.role == "member":
        query = query.filter(Activity.status == "published")
    elif status_filter:
        query = query.filter(Activity.status == status_filter)

    if search:
        search_term = f"%{search}%"
        query = query.filter(Activity.name.ilike(search_term))

    query = query.order_by(Activity.id.desc())
    items, meta = paginate(query, page, per_page)

    return {
        "meta": meta.model_dump(),
        "items": [_to_list_response(a) for a in items],
    }


@router.get("/{activity_id}", response_model=ActivityResponse)
def get_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Members can only see published activities
    if current_user.role == "member" and activity.status != "published":
        raise HTTPException(status_code=404, detail="Activity not found")

    return _to_response(activity)


@router.post("/", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
def create_activity_endpoint(
    data: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    activity = create_activity(db, data, current_user.id)
    db.commit()
    db.refresh(activity)
    return _to_response(activity)


@router.put("/{activity_id}", response_model=ActivityResponse)
def update_activity_endpoint(
    activity_id: int,
    data: ActivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    activity = get_or_404(db, Activity, activity_id)
    activity = update_activity(db, activity, data)
    db.commit()
    db.refresh(activity)
    return _to_response(activity)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    activity = get_or_404(db, Activity, activity_id)
    if activity.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft activities can be deleted",
        )
    activity.is_active = False
    db.commit()


@router.put("/{activity_id}/publish", response_model=ActivityResponse)
def publish_activity_endpoint(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    activity = get_or_404(db, Activity, activity_id)
    activity = publish_activity(db, activity)
    db.commit()
    db.refresh(activity)
    return _to_response(activity)


@router.put("/{activity_id}/archive", response_model=ActivityResponse)
def archive_activity_endpoint(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    activity = get_or_404(db, Activity, activity_id)
    activity = archive_activity(db, activity)
    db.commit()
    db.refresh(activity)
    return _to_response(activity)


@router.put("/{activity_id}/cancel", response_model=ActivityResponse)
def cancel_activity_endpoint(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    activity = get_or_404(db, Activity, activity_id)
    activity = cancel_activity(db, activity)
    db.commit()
    db.refresh(activity)
    return _to_response(activity)
