"""Reminders service — admin notes & dated reminders CRUD.

Kept deliberately minimal (single flat table, no assignment/recurrence/
notifications). Callers commit; these helpers flush so the caller sees the row.
"""

from app.domains.reminders.models import Reminder
from app.domains.reminders.schemas import ReminderCreate, ReminderUpdate

from sqlalchemy.orm import Session


def list_reminders(db: Session, *, only_open: bool = False) -> list[Reminder]:
    """List reminders. Order: open first, then due date (nulls last), newest first.

    ``only_open`` (used by the dashboard rail) hides done items.
    """
    query = db.query(Reminder)
    if only_open:
        query = query.filter(Reminder.is_done.is_(False))
    return (
        query.order_by(
            Reminder.is_done.asc(),
            Reminder.due_date.asc().nulls_last(),
            Reminder.created_at.desc(),
        )
        .all()
    )


def get_reminder(db: Session, reminder_id: int) -> Reminder | None:
    return db.get(Reminder, reminder_id)


def create_reminder(db: Session, data: ReminderCreate, created_by: int | None) -> Reminder:
    reminder = Reminder(
        content=data.content,
        due_date=data.due_date,
        created_by=created_by,
    )
    db.add(reminder)
    db.flush()
    return reminder


def update_reminder(db: Session, reminder: Reminder, data: ReminderUpdate) -> Reminder:
    """Apply only the fields the client actually sent.

    ``exclude_unset`` distinguishes "clear the due date" (``due_date: null``,
    turning a reminder back into a note) from "leave it untouched" (omitted).
    """
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(reminder, field, value)
    db.flush()
    return reminder


def delete_reminder(db: Session, reminder: Reminder) -> None:
    db.delete(reminder)
    db.flush()
