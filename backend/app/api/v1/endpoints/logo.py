"""Organization logo upload and delete endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings
from app.core.file_replace import remove_files, replace_file
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.organizations.models import OrganizationSettings

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "svg"}
MAX_LOGO_SIZE_MB = 5

router = APIRouter(prefix="/settings/logo", tags=["settings"])


@router.post("/", status_code=status.HTTP_200_OK)
async def upload_logo(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.write")),
):
    """Upload or replace the organization logo."""
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Validate file extension
    ext = ""
    if file.filename and "." in file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}",
        )

    # Validate content type
    if not file.content_type or not (
        file.content_type.startswith("image/") or file.content_type == "image/svg+xml"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image",
        )

    # Read and validate size
    content = await file.read()
    file_size = len(content)
    if file_size > MAX_LOGO_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum size of {MAX_LOGO_SIZE_MB}MB",
        )

    def commit(filename: str) -> None:
        org.logo_url = f"/uploads/org/{filename}"
        db.commit()

    replace_file(Path(settings.STORAGE_LOCAL_PATH) / "org", "logo", ext, content, commit)
    db.refresh(org)

    return {"logo_url": org.logo_url}


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def delete_logo(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.write")),
):
    """Delete the organization logo."""
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org or not org.logo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No logo to delete",
        )

    org.logo_url = None
    db.commit()
    remove_files(Path(settings.STORAGE_LOCAL_PATH) / "org", "logo")
