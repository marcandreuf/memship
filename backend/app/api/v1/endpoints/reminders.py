"""Reminders endpoints — admin notes & dated reminders.

A note has no due date; a reminder has one. Shown in the dashboard rail
(open items first). Admin-only; single-tenant so no org scoping.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.reminders import service
from app.domains.reminders.schemas import (
    ReminderCreate,
    ReminderRead,
    ReminderUpdate,
)

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("", response_model=list[ReminderRead])
def list_reminders(
    only_open: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reminders.read")),
):
    """List reminders; ``only_open=true`` (the rail default) hides done items."""
    return service.list_reminders(db, only_open=only_open)


@router.post("", response_model=ReminderRead, status_code=status.HTTP_201_CREATED)
def create_reminder(
    data: ReminderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reminders.write")),
):
    reminder = service.create_reminder(db, data, created_by=current_user.id)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.patch("/{reminder_id}", response_model=ReminderRead)
def update_reminder(
    reminder_id: int,
    data: ReminderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reminders.write")),
):
    reminder = service.get_reminder(db, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    reminder = service.update_reminder(db, reminder, data)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reminders.write")),
):
    reminder = service.get_reminder(db, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    service.delete_reminder(db, reminder)
    db.commit()
