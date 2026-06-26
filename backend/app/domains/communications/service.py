"""Communications service — announcement authoring, sending, and notifications.

The send path resolves the audience once, snapshots ``recipient_count``, writes
in-app ``Notification`` rows synchronously (so the badge updates immediately),
and leaves the slower email fan-out to a Celery task. Does not commit — the
caller (endpoint / task) owns the transaction.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domains.auth.models import User
from app.domains.communications.markdown import excerpt as build_excerpt
from app.domains.communications.models import Announcement, Notification
from app.domains.communications.schemas import (
    AnnouncementCreate,
    AnnouncementUpdate,
    validate_target,
)
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person


class AnnouncementNotDraft(Exception):
    """Raised when an operation requires a draft but the announcement is sent."""


class EmptyAudience(Exception):
    """Raised when a send resolves to zero recipients."""


# --- Authoring ---


def create_announcement(
    db: Session, data: AnnouncementCreate, user: User
) -> Announcement:
    """Create a draft announcement. Target already validated by the schema."""
    ann = Announcement(
        subject=data.subject,
        body=data.body,
        target_type=data.target_type,
        target_id=data.target_id,
        status="draft",
        created_by_user_id=user.id,
    )
    db.add(ann)
    db.flush()
    return ann


def update_announcement(
    db: Session, announcement_id: int, data: AnnouncementUpdate
) -> Announcement | None:
    """Edit a draft. Returns None if not found; raises if already sent."""
    ann = _get_active(db, announcement_id)
    if ann is None:
        return None
    if ann.status != "draft":
        raise AnnouncementNotDraft()

    fields = data.model_fields_set
    if "subject" in fields and data.subject is not None:
        ann.subject = data.subject
    if "body" in fields and data.body is not None:
        ann.body = data.body
    if "target_type" in fields and data.target_type is not None:
        ann.target_type = data.target_type
    if "target_id" in fields:
        ann.target_id = data.target_id
    if fields & {"target_type", "target_id"}:
        validate_target(ann.target_type, ann.target_id)  # raises ValueError
    db.flush()
    return ann


# --- Audience ---


def resolve_audience(
    db: Session, target_type: str, target_id: int | None
) -> list[Member]:
    """Active members matching the target (all / group / membership type)."""
    query = db.query(Member).filter(
        Member.is_active.is_(True), Member.status == "active"
    )
    if target_type == "group":
        query = query.join(
            MembershipType, Member.membership_type_id == MembershipType.id
        ).filter(MembershipType.group_id == target_id)
    elif target_type == "membership_type":
        query = query.filter(Member.membership_type_id == target_id)
    return query.all()


def email_recipients(db: Session, members: list[Member]) -> list[Person]:
    """Persons reachable by email — has an email and hasn't opted out of email."""
    out: list[Person] = []
    for member in members:
        prefs = member.communication_preferences or {}
        if prefs.get("email") is False:
            continue
        person = db.query(Person).filter(Person.id == member.person_id).first()
        if person and person.email:
            out.append(person)
    return out


# --- Sending ---


def send_announcement(
    db: Session, announcement_id: int, user: User
) -> Announcement | None:
    """Resolve the audience, snapshot it, create notifications, flip to sent.

    Returns None if not found. Raises ``AnnouncementNotDraft`` if already sent
    and ``EmptyAudience`` if the target resolves to no members. The email
    fan-out is enqueued by the caller after commit. Does not commit.
    """
    ann = _get_active(db, announcement_id)
    if ann is None:
        return None
    if ann.status != "draft":
        raise AnnouncementNotDraft()

    members = resolve_audience(db, ann.target_type, ann.target_id)
    if not members:
        raise EmptyAudience()

    ann.recipient_count = len(members)
    excerpt = build_excerpt(ann.body)
    # In-app notifications require a user account (email is the universal channel).
    user_ids = {m.user_id for m in members if m.user_id}
    for uid in user_ids:
        db.add(
            Notification(
                user_id=uid,
                source_type="announcement",
                source_id=ann.id,
                title=ann.subject,
                excerpt=excerpt,
            )
        )

    ann.status = "sent"
    ann.sent_at = datetime.now(timezone.utc)
    db.flush()
    return ann


# --- Reads ---


def list_announcements(db: Session):
    """Admin history query (drafts + sent), newest first. Caller paginates."""
    return (
        db.query(Announcement)
        .filter(Announcement.is_active.is_(True))
        .order_by(Announcement.created_at.desc(), Announcement.id.desc())
    )


def get_announcement(db: Session, announcement_id: int) -> Announcement | None:
    return _get_active(db, announcement_id)


def member_announcements(db: Session, user: User) -> list[Announcement]:
    """Announcements the user received, via their notifications, newest first."""
    return (
        db.query(Announcement)
        .join(Notification, Notification.source_id == Announcement.id)
        .filter(
            Notification.user_id == user.id,
            Notification.source_type == "announcement",
            Announcement.is_active.is_(True),
        )
        .order_by(Notification.created_at.desc(), Announcement.id.desc())
        .all()
    )


def list_notifications(db: Session, user: User) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .all()
    )


def unread_count(db: Session, user: User) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .count()
    )


def mark_read(
    db: Session, user: User, ids: list[int] | None = None, all_: bool = False
) -> int:
    """Mark the user's unread notifications read (by ids, or all). Returns count."""
    query = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    )
    if not all_:
        if not ids:
            return 0
        query = query.filter(Notification.id.in_(ids))
    now = datetime.now(timezone.utc)
    updated = query.update({Notification.read_at: now}, synchronize_session=False)
    db.flush()
    return updated


def _get_active(db: Session, announcement_id: int) -> Announcement | None:
    return (
        db.query(Announcement)
        .filter(Announcement.id == announcement_id, Announcement.is_active.is_(True))
        .first()
    )
