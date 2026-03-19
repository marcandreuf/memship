"""Activity attachment type endpoints + registration file upload."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.config import settings
from app.core.db_utils import get_or_404
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.activities.attachment_schemas import (
    ActivityAttachmentTypeCreate,
    ActivityAttachmentTypeResponse,
    ActivityAttachmentTypeUpdate,
    RegistrationAttachmentResponse,
)
from app.domains.activities.models import (
    Activity,
    ActivityAttachmentType,
    Registration,
    RegistrationAttachment,
)
from app.domains.auth.models import User
from app.domains.members.models import Member

# --- Activity attachment type CRUD ---

router = APIRouter(prefix="/activities/{activity_id}/attachment-types", tags=["activity-attachments"])


@router.get("/", response_model=list[ActivityAttachmentTypeResponse])
def list_attachment_types(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List attachment types for an activity (all authenticated users)."""
    get_or_404(db, Activity, activity_id)
    return (
        db.query(ActivityAttachmentType)
        .filter(
            ActivityAttachmentType.activity_id == activity_id,
            ActivityAttachmentType.is_active.is_(True),
        )
        .order_by(ActivityAttachmentType.display_order)
        .all()
    )


@router.post("/", response_model=ActivityAttachmentTypeResponse, status_code=status.HTTP_201_CREATED)
def create_attachment_type(
    activity_id: int,
    data: ActivityAttachmentTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create an attachment type for an activity (admin only)."""
    get_or_404(db, Activity, activity_id)
    att_type = ActivityAttachmentType(activity_id=activity_id, **data.model_dump())
    db.add(att_type)
    db.commit()
    db.refresh(att_type)
    return att_type


@router.put("/{type_id}", response_model=ActivityAttachmentTypeResponse)
def update_attachment_type(
    activity_id: int,
    type_id: int,
    data: ActivityAttachmentTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update an attachment type (admin only)."""
    att_type = get_or_404(db, ActivityAttachmentType, type_id)
    if att_type.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Attachment type not found for this activity")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(att_type, key, value)
    db.commit()
    db.refresh(att_type)
    return att_type


@router.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment_type(
    activity_id: int,
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete an attachment type (admin only)."""
    att_type = get_or_404(db, ActivityAttachmentType, type_id)
    if att_type.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Attachment type not found for this activity")
    db.delete(att_type)
    db.commit()


# --- Registration attachment upload ---

upload_router = APIRouter(tags=["registration-attachments"])


@upload_router.get(
    "/registrations/{registration_id}/attachments",
    response_model=list[RegistrationAttachmentResponse],
)
def list_registration_attachments(
    registration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List attachments for a registration."""
    registration = get_or_404(db, Registration, registration_id)

    # Check access: admin or own registration
    is_admin = current_user.role in ("admin", "super_admin")
    if not is_admin:
        member = db.query(Member).filter(Member.user_id == current_user.id).first()
        if not member or registration.member_id != member.id:
            raise HTTPException(status_code=403, detail="Access denied")

    return (
        db.query(RegistrationAttachment)
        .filter(RegistrationAttachment.registration_id == registration_id)
        .order_by(RegistrationAttachment.uploaded_at)
        .all()
    )


@upload_router.post(
    "/registrations/{registration_id}/attachments",
    response_model=RegistrationAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_registration_attachment(
    registration_id: int,
    file: UploadFile,
    attachment_type_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a file attachment for a registration."""
    registration = get_or_404(db, Registration, registration_id)

    # Check access: admin or own registration
    is_admin = current_user.role in ("admin", "super_admin")
    if not is_admin:
        member = db.query(Member).filter(Member.user_id == current_user.id).first()
        if not member or registration.member_id != member.id:
            raise HTTPException(status_code=403, detail="Access denied")

    # Validate against attachment type if provided
    att_type = None
    if attachment_type_id:
        att_type = db.query(ActivityAttachmentType).filter(
            ActivityAttachmentType.id == attachment_type_id,
            ActivityAttachmentType.is_active.is_(True),
        ).first()
        if not att_type:
            raise HTTPException(status_code=400, detail="Invalid attachment type")

        # Check extension
        if att_type.allowed_extensions and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
            if ext not in [e.lower() for e in att_type.allowed_extensions]:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '.{ext}' not allowed. Allowed: {', '.join(att_type.allowed_extensions)}",
                )

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Check file size
    max_size_mb = att_type.max_file_size_mb if att_type else settings.MAX_UPLOAD_SIZE_MB
    if file_size > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size of {max_size_mb}MB",
        )

    # Save file
    storage_dir = Path(settings.STORAGE_LOCAL_PATH) / "registrations" / str(registration_id)
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename to avoid collisions
    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = storage_dir / unique_name

    with open(file_path, "wb") as f:
        f.write(content)

    # Save record
    attachment = RegistrationAttachment(
        registration_id=registration_id,
        attachment_type_id=attachment_type_id,
        file_name=file.filename or unique_name,
        file_path=str(file_path),
        file_size=file_size,
        mime_type=file.content_type,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment
