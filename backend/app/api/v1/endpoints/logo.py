"""Organization logo upload and delete endpoints."""

import glob
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.authorization import require_super_admin
from app.core.config import settings
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
    current_user: User = Depends(require_super_admin),
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

    # Delete existing logo files
    storage_dir = Path(settings.STORAGE_LOCAL_PATH) / "org"
    storage_dir.mkdir(parents=True, exist_ok=True)
    for old_file in glob.glob(str(storage_dir / "logo.*")):
        Path(old_file).unlink(missing_ok=True)

    # Save new file
    filename = f"logo.{ext}"
    file_path = storage_dir / filename
    with open(file_path, "wb") as f:
        f.write(content)

    # Update settings
    org.logo_url = f"/uploads/org/{filename}"
    db.commit()
    db.refresh(org)

    return {"logo_url": org.logo_url}


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def delete_logo(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Delete the organization logo."""
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org or not org.logo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No logo to delete",
        )

    # Delete files from disk
    storage_dir = Path(settings.STORAGE_LOCAL_PATH) / "org"
    for old_file in glob.glob(str(storage_dir / "logo.*")):
        Path(old_file).unlink(missing_ok=True)

    # Clear DB
    org.logo_url = None
    db.commit()
