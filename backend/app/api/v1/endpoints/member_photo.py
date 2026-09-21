"""Member self-service profile photo upload / delete.

Sets ``persons.photo_url`` for the current user's person, so the member card
(web + PDF) shows a real photo instead of the initials placeholder. Stored on
the local filesystem and served via the ``/uploads`` proxy, mirroring the
activity cover-image pattern.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.file_replace import remove_files, replace_file
from app.core.security.dependencies import get_current_user
from app.core.authorization import require_permission
from app.db.session import get_db
from app.domains.auth.models import User

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

router = APIRouter(prefix="/members/me/photo", tags=["member-photo"])


def _photo_dir(person_id: int) -> Path:
    return Path(settings.STORAGE_LOCAL_PATH) / "members" / str(person_id)


@router.post("/", status_code=status.HTTP_200_OK)
async def upload_my_photo(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.profile.write")),
):
    """Upload or replace the current member's profile photo."""
    person = current_user.person

    ext = ""
    if file.filename and "." in file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}",
        )

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image",
        )

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    def commit(filename: str) -> None:
        person.photo_url = f"/uploads/members/{person.id}/{filename}"
        db.commit()

    replace_file(_photo_dir(person.id), "photo", ext, content, commit)

    return {"photo_url": person.photo_url}


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_photo(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.profile.write")),
):
    """Remove the current member's profile photo (card falls back to initials)."""
    person = current_user.person
    if not person.photo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No photo to delete",
        )

    person.photo_url = None
    db.commit()
    remove_files(_photo_dir(person.id), "photo")
