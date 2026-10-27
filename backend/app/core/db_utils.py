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


def get_person_by_party_or_404(db: Session, party_id: int):
    """Resolve a person by the party id — the id the API exposes (ADR 0003).

    ``persons.id`` still exists for the polymorphic addresses/contacts pattern
    and dies with it; nothing API-facing should resolve through it.
    """
    from app.domains.persons.models import Person

    person = db.query(Person).filter(Person.party_id == party_id).first()
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        )
    return person


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

    Resolved through the party: login and membership both hang off
    ``party_id`` (ADR 0003), so the caller's member row is the one sharing the
    user's party. Never resolved through ``Person.email``: that column is
    non-unique and a minor routinely shares a guardian's address, so an email
    match can return somebody else's member row.

    A partial unique index (``uq_members_one_active_per_party``, migration
    ``29a3872dad10``) makes a second active row impossible. The ordering below
    is kept anyway: it costs nothing against a unique column, and it is the
    rule the repoint migration used to decide which of any pre-existing
    duplicate stayed active, so the two stay in lockstep (#187).
    """
    from app.domains.members.models import Member

    query = (
        db.query(Member)
        .options(joinedload(Member.person))
        .filter(Member.party_id == user.party_id)
        .order_by(Member.is_active.desc(), Member.id.desc())
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
