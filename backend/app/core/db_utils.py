"""Database utility helpers."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import Base


def get_or_404(db: Session, model: type[Base], id: int, detail: str | None = None):
    instance = db.query(model).filter(model.id == id).first()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail or f"{model.__name__} not found",
        )
    return instance
