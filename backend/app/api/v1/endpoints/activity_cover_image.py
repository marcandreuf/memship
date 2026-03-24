"""Activity cover image upload and delete endpoints."""

import glob
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.config import settings
from app.core.db_utils import get_or_404
from app.db.session import get_db
from app.domains.activities.models import Activity
from app.domains.auth.models import User

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}

router = APIRouter(prefix="/activities/{activity_id}/cover-image", tags=["activity-cover-image"])


@router.post("/", status_code=status.HTTP_200_OK)
async def upload_cover_image(
    activity_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Upload or replace the cover image for an activity."""
    activity = get_or_404(db, Activity, activity_id)

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
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image",
        )

    # Read and validate size
    content = await file.read()
    file_size = len(content)
    if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # Delete existing cover files
    storage_dir = Path(settings.STORAGE_LOCAL_PATH) / "activities" / str(activity_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    for old_file in glob.glob(str(storage_dir / "cover.*")):
        Path(old_file).unlink(missing_ok=True)

    # Save new file
    filename = f"cover.{ext}"
    file_path = storage_dir / filename
    with open(file_path, "wb") as f:
        f.write(content)

    # Update activity
    activity.image_url = f"/uploads/activities/{activity_id}/{filename}"
    db.commit()
    db.refresh(activity)

    return {"image_url": activity.image_url}


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def delete_cover_image(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete the cover image for an activity."""
    activity = get_or_404(db, Activity, activity_id)

    if not activity.image_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cover image to delete",
        )

    # Delete files from disk
    storage_dir = Path(settings.STORAGE_LOCAL_PATH) / "activities" / str(activity_id)
    for old_file in glob.glob(str(storage_dir / "cover.*")):
        Path(old_file).unlink(missing_ok=True)

    # Clear DB
    activity.image_url = None
    db.commit()
