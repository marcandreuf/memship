"""A person's gender, checked against the values the organization offers.

``features.gender_options`` is the closed set the UI renders a select from; a
value outside it has no label in any locale and shows as blank everywhere.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domains.organizations.models import OrganizationSettings


def offered_genders(db: Session) -> set[str]:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    options = ((org.features if org else None) or {}).get("gender_options") or []
    return {o["value"] for o in options if isinstance(o, dict) and o.get("value")}


def require_offered_gender(db: Session, value: str | None, current: str | None = None) -> None:
    """Refuse a gender the organization does not offer.

    Clearing it is always allowed, and so is resubmitting the value already
    stored: an option withdrawn after it was chosen must not lock the rest of
    the record against editing, since every edit form sends it back unchanged.
    """
    if value is None or value == current:
        return
    if value not in offered_genders(db):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Gender '{value}' is not one of the organization's options",
        )
