"""Import every model module so the SQLAlchemy mapper registry is complete.

Processes that don't load the full API (e.g. the Celery worker/beat) must import
this module before running any query, otherwise string-based relationships such as
``Receipt`` -> ``Registration`` fail to resolve during mapper configuration.
"""

from app.domains.activities import models as activities_models  # noqa: F401
from app.domains.audit import models as audit_models  # noqa: F401
from app.domains.auth import models as auth_models  # noqa: F401
from app.domains.billing import models as billing_models  # noqa: F401
from app.domains.communications import models as communications_models  # noqa: F401
from app.domains.members import models as members_models  # noqa: F401
from app.domains.organizations import models as organizations_models  # noqa: F401
from app.domains.persons import models as persons_models  # noqa: F401
from app.domains.reminders import models as reminders_models  # noqa: F401
