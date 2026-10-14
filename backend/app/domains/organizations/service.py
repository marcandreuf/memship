"""Organization settings — reads of the single ``id = 1`` row."""

from sqlalchemy.orm import Session

from app.domains.organizations.models import OrganizationSettings

DEFAULT_LOCALE = "es"


def org_locale(db: Session) -> str:
    """The language the organization is configured in.

    Member-facing mail and the links inside it render in this. It lives on the
    single ``organization_settings`` row — there is no per-member language
    column — so it is the only locale available and the only correct source.
    ``settings.DEFAULT_LOCALE`` is an environment default, not what the club
    chose on the Settings screen, which is why it is not used for this (#362).

    The same expression was written out in eight places with three different
    fallback spellings. This is the one copy; the others are worth folding in
    as they are touched.
    """
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    return (org.locale if org else None) or DEFAULT_LOCALE
