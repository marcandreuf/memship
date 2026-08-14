"""Authenticated access to files stored under ``STORAGE_LOCAL_PATH``.

Everything the product persists lives under one directory: the Fernet key that
decrypts stored SSO and payment-provider secrets, generated SEPA remittance
files, scanned mandates, member photos and registration attachments. That
directory used to be mounted with ``StaticFiles``, which serves whatever is
asked for to whoever asks — no session, no ownership check.

This router replaces that mount. A path is served only when it matches one of
the rules in :data:`_GUARDS` (or the public prefix list), so anything without a
rule — ``secret.key``, the remittance XML, a future writer that nobody thought
about — is a 404. Remittances keep their own authenticated download endpoint
(``GET /api/v1/remittances/{id}/download-xml``) and do not need one here.

Paths stay exactly as they are stored in the database (``/uploads/org/logo.png``
and friends), so nothing has to be migrated.
"""

import mimetypes
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.authorization import resolve_permissions
from app.core.config import settings
from app.core.security.dependencies import get_optional_user
from app.db.session import get_db
from app.domains.activities.models import Registration
from app.domains.auth.models import User
from app.domains.members.models import Member

router = APIRouter(prefix="/uploads", tags=["uploads"])

# The organisation logo is branding shown before anyone is signed in, so it is
# the one prefix served without a session.
_PUBLIC_PREFIXES = frozenset({"org"})

# Rendered inline; everything else is forced to download so an uploaded file can
# never execute as a page on the application's own origin. SVG stays image/* so
# it still renders in an <img> (which ignores Content-Disposition) while direct
# navigation downloads it instead of running its script.
_INLINE_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
)


def _own_member(db: Session, user: User) -> Member | None:
    return db.query(Member).filter(Member.user_id == user.id).first()


def _allow_activities(db: Session, user: User, rest: list[str]) -> bool:
    """Activity cover images — any signed-in user."""
    return True


def _allow_members(db: Session, user: User, rest: list[str]) -> bool:
    """``members/<person_id>/photo.<ext>`` — the member themselves, or staff."""
    if user.person_id is not None and str(user.person_id) == rest[0]:
        return True
    return "members.read" in resolve_permissions(user)


def _allow_mandates(db: Session, user: User, rest: list[str]) -> bool:
    """``mandates/<member_id>/<ref>.<ext>`` — the signing member, or billing staff."""
    if "billing.read" in resolve_permissions(user):
        return True
    member = _own_member(db, user)
    return member is not None and str(member.id) == rest[0]


def _allow_registrations(db: Session, user: User, rest: list[str]) -> bool:
    """``registrations/<registration_id>/<uuid>.<ext>`` — the registered member, or staff."""
    if "registrations.read" in resolve_permissions(user):
        return True
    member = _own_member(db, user)
    if member is None or not rest[0].isdigit():
        return False
    return (
        db.query(Registration.id)
        .filter(
            Registration.id == int(rest[0]),
            Registration.member_id == member.id,
        )
        .first()
        is not None
    )


_GUARDS = {
    "activities": _allow_activities,
    "members": _allow_members,
    "mandates": _allow_mandates,
    "registrations": _allow_registrations,
}


def _not_found() -> HTTPException:
    """Deliberately the same answer for "no such file" and "not yours", so the
    predictable filenames (member numbers, mandate references) cannot be
    enumerated through the difference."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")


def _resolve_within_storage(parts: list[str]) -> Path:
    root = Path(settings.STORAGE_LOCAL_PATH).resolve()
    candidate = root.joinpath(*parts).resolve()
    if candidate != root and root not in candidate.parents:
        raise _not_found()
    return candidate


@router.get("/{path:path}")
def serve_upload(
    path: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    parts = [p for p in PurePosixPath(path).parts if p not in ("", ".")]
    if not parts or ".." in parts:
        raise _not_found()

    prefix, rest = parts[0], parts[1:]

    if prefix not in _PUBLIC_PREFIXES:
        guard = _GUARDS.get(prefix)
        if guard is None or not rest:
            raise _not_found()
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        if not guard(db, current_user, rest):
            raise _not_found()

    file_path = _resolve_within_storage(parts)
    if not file_path.is_file():
        raise _not_found()

    media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    if media_type in _INLINE_TYPES:
        disposition = "inline"
    else:
        disposition = "attachment"
        if media_type != "image/svg+xml":
            media_type = "application/octet-stream"

    return FileResponse(
        file_path,
        media_type=media_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{file_path.name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600"
            if prefix not in _PUBLIC_PREFIXES
            else "public, max-age=3600",
        },
    )