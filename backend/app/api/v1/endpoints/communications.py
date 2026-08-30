"""Communications endpoints — admin announcements + member notifications."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.pagination import paginate
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.communications import service
from app.domains.communications.schemas import (
    AnnouncementCreate,
    AnnouncementResponse,
    AnnouncementUpdate,
    MarkReadRequest,
    NotificationResponse,
    RecipientResponse,
    RecipientStatsResponse,
)
from app.domains.communications.service import (
    AnnouncementNotDraft,
    EmptyAudience,
)
from app.domains.organizations.models import OrganizationSettings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/announcements", tags=["communications"])
me_router = APIRouter(prefix="/me", tags=["communications"])


def _require_communications_enabled(db: Session) -> None:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    features = (org.features or {}) if org else {}
    if not features.get("communications"):
        raise HTTPException(status_code=404, detail="Not found")


# --- Admin: announcements ---


@router.post("", status_code=status.HTTP_201_CREATED)
def create_announcement(
    data: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("communications.write")),
):
    """Create a draft announcement."""
    _require_communications_enabled(db)
    ann = service.create_announcement(db, data, current_user)
    db.commit()
    return AnnouncementResponse.model_validate(ann).model_dump()


@router.get("")
def list_announcements(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("communications.read")),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Admin history of drafts + sent announcements, newest first."""
    _require_communications_enabled(db)
    items, meta = paginate(service.list_announcements(db), page, per_page)
    return {
        "items": [AnnouncementResponse.model_validate(a).model_dump() for a in items],
        "meta": meta.model_dump(),
    }


@router.get("/{announcement_id}")
def get_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("communications.read")),
):
    _require_communications_enabled(db)
    ann = service.get_announcement(db, announcement_id)
    if ann is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    return AnnouncementResponse.model_validate(ann).model_dump()


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: int,
    data: AnnouncementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("communications.write")),
):
    """Edit a draft. 409 if already sent, 422 if the target is inconsistent."""
    _require_communications_enabled(db)
    try:
        ann = service.update_announcement(db, announcement_id, data)
    except AnnouncementNotDraft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A sent announcement cannot be edited",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if ann is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    db.commit()
    return AnnouncementResponse.model_validate(ann).model_dump()


@router.post("/{announcement_id}/send")
def send_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("communications.send")),
):
    """Resolve the audience, deliver in-app notifications, enqueue email, flip to sent."""
    _require_communications_enabled(db)
    try:
        ann = service.send_announcement(db, announcement_id, current_user)
    except AnnouncementNotDraft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Announcement has already been sent",
        )
    except EmptyAudience:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The selected audience has no members",
        )
    if ann is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    db.commit()

    # Enqueue the email fan-out. A broker hiccup must not fail the send — the
    # in-app notifications already landed (committed above).
    try:
        from app.tasks.communication_tasks import send_announcement_task

        send_announcement_task.delay(ann.id)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to enqueue announcement email fan-out: {exc}")

    return AnnouncementResponse.model_validate(ann).model_dump()


@router.get("/{announcement_id}/audience-preview")
def audience_preview(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("communications.read")),
):
    """Audience size for the announcement's current target (compose preview)."""
    _require_communications_enabled(db)
    ann = service.get_announcement(db, announcement_id)
    if ann is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    members = service.resolve_audience(db, ann.target_type, ann.target_id)
    return {"count": len(members)}


@router.get("/{announcement_id}/recipients")
def list_recipients(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("communications.read")),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Paginated recipient list for a sent announcement (name, channel, seen)."""
    _require_communications_enabled(db)
    ann = service.get_announcement(db, announcement_id)
    if ann is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    rows, meta = paginate(service.list_recipients(db, announcement_id), page, per_page)
    items = [
        RecipientResponse(
            member_id=r.member_id,
            name=f"{r.first_name} {r.last_name}".strip(),
            email=r.email,
            emailed=r.emailed,
            in_app=r.in_app,
            seen_at=r.read_at,
        ).model_dump()
        for r in rows
    ]
    return {"items": items, "meta": meta.model_dump()}


@router.get("/{announcement_id}/stats")
def recipient_stats(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("communications.read")),
):
    """Aggregate delivery stats (recipients / emailed / seen) for the sent view."""
    _require_communications_enabled(db)
    ann = service.get_announcement(db, announcement_id)
    if ann is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    return RecipientStatsResponse(**service.recipient_stats(db, announcement_id)).model_dump()


# --- Member: received announcements + in-app notifications ---


@me_router.get("/announcements")
def my_announcements(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.communications.read")),
):
    """Announcements the current user received, newest first."""
    _require_communications_enabled(db)
    items = service.member_announcements(db, current_user)
    return [AnnouncementResponse.model_validate(a).model_dump() for a in items]


@me_router.get("/notifications")
def my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.communications.read")),
):
    _require_communications_enabled(db)
    items = service.list_notifications(db, current_user)
    return [NotificationResponse.model_validate(n).model_dump() for n in items]


@me_router.get("/notifications/unread-count")
def my_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.communications.read")),
):
    _require_communications_enabled(db)
    return {"count": service.unread_count(db, current_user)}


@me_router.post("/notifications/mark-read")
def mark_notifications_read(
    data: MarkReadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.communications.write")),
):
    _require_communications_enabled(db)
    updated = service.mark_read(db, current_user, ids=data.ids, all_=data.all)
    db.commit()
    return {"updated": updated}
