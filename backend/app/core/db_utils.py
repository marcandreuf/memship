"""Database utility helpers."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.db.base import Base


def get_or_404(db: Session, model: type[Base], id: int, detail: str | None = None):
    instance = db.query(model).filter(model.id == id).first()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail or f"{model.__name__} not found",
        )
    return instance


def current_member_or_403(db: Session, user, *, active_only: bool = False):
    """The caller's own member record, or one refusal that says why there isn't one.

    An account can be signed in, hold every ``self.*`` permission, and still have
    no member record: a super admin or club admin administers the instance
    without belonging to the club (#168). The ``self.*`` keys are the floor on
    the endpoints staff and members share — `members.py:152` and
    `receipts.py:312` widen from them rather than branch on them — so they are
    not what tells the two apart. The member record is.

    403 rather than 404: the request is well formed and the caller is known,
    what is missing is a membership. The ``code`` is what lets a caller say that
    instead of rendering a generic failure, the same way ``pending_approval``
    does in `security/dependencies.py`.

    ``active_only`` keeps the distinction the call sites already make: billing
    routes resolve only a live membership, while the card and the booking
    routes answer for a cancelled member too.

    Resolved through ``Member.user_id``, never through ``Person.email``: that
    column is non-unique and a minor routinely shares a guardian's address, so
    an email match can return somebody else's member row.
    """
    from app.domains.members.models import Member

    query = db.query(Member).options(joinedload(Member.person)).filter(
        Member.user_id == user.id
    )
    if active_only:
        query = query.filter(Member.is_active.is_(True))

    member = query.first()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "not_a_member",
                "message": "This account has no member record",
            },
        )
    return member
