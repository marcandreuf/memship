"""Integration test fixtures — requires a running PostgreSQL database."""

import os

import pytest
from argon2 import PasswordHasher
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security.password as _pw_module
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Stub password hashing for tests: use fast argon2 params and cache results.
# Production argon2 uses time_cost=3, memory_cost=65536 (~60ms/hash on dev, ~300ms on CI).
# With ~500 hash calls across 221 tests, this saves minutes of CI time.
# Each unique password is hashed once with minimal params, then reused from cache.
_fast_ph = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)
_hash_cache: dict[str, str] = {}


def _cached_hash(password: str) -> str:
    if password not in _hash_cache:
        _hash_cache[password] = _fast_ph.hash(password)
    return _hash_cache[password]


_pw_module.ph = _fast_ph  # for verify_password (reads params from hash string)
_pw_module.hash_password = _cached_hash

# Import all models so Base.metadata knows about them
from app.domains.organizations.models import OrganizationSettings  # noqa: F401
from app.domains.persons.models import (  # noqa: F401
    Address,
    AddressType,
    Contact,
    ContactType,
    Person,
)
from app.domains.auth.models import User, UserIdentity  # noqa: F401
from app.domains.members.models import Group, Member, MembershipType  # noqa: F401
from app.domains.audit.models import AuditLog  # noqa: F401
from app.domains.activities.models import (  # noqa: F401
    Activity, ActivityAttachmentType, ActivityConsent, ActivityModality,
    ActivityPrice, DiscountCode, Registration, RegistrationAttachment,
    RegistrationConsent,
)
from app.domains.billing.models import (  # noqa: F401
    BillingRun, Concept, PaymentProvider, Receipt, Remittance, SepaMandate, WebhookEvent,
)
from app.domains.communications.models import (  # noqa: F401
    Announcement,
    AnnouncementRecipient,
    Notification,
)
from app.domains.reminders.models import Reminder  # noqa: F401
from app.domains.custom_fields.models import (  # noqa: F401
    CustomFieldDefinition,
    CustomFieldValue,
)

# Use test database
BASE_TEST_DATABASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)


def _worker_database_url(base_url: str) -> str:
    """Give each pytest-xdist worker its own database.

    Every test holds an open transaction until teardown rolls it back. Two
    workers sharing one database therefore block on each other's uncommitted
    rows whenever they insert the same unique key (``membership_types.name``,
    ``organization_settings.id = 1``, person emails, ...), which escalates to
    ``DeadlockDetected`` as soon as the lock waits cross. Isolating the schema
    per worker removes the contention entirely.

    Creates the per-worker database on first use; no-op when running without
    xdist or against SQLite.
    """
    worker = os.getenv("PYTEST_XDIST_WORKER")
    if not worker:
        return base_url

    from sqlalchemy import text
    from sqlalchemy.engine.url import make_url
    from sqlalchemy.exc import ProgrammingError

    url = make_url(base_url)
    if not url.get_backend_name().startswith("postgresql"):
        return base_url

    worker_db = f"{url.database}_{worker}"
    admin_engine = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": worker_db},
            ).scalar()
            if not exists:
                try:
                    conn.execute(text(f'CREATE DATABASE "{worker_db}"'))
                except ProgrammingError:
                    # Lost the race against another worker — it exists now.
                    pass
    finally:
        admin_engine.dispose()

    return url.set(database=worker_db).render_as_string(hide_password=False)


TEST_DATABASE_URL = _worker_database_url(BASE_TEST_DATABASE_URL)
test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """Create all tables once per test session (per xdist worker database).

    create_all uses IF NOT EXISTS for most DDL, but PostgreSQL type
    creation can race, so the error is caught and ignored.
    Skips drop_all — the test DB is ephemeral (CI service or local docker).
    """
    from sqlalchemy.exc import IntegrityError

    try:
        Base.metadata.create_all(bind=test_engine)
    except IntegrityError:
        # Another xdist worker already created the tables — safe to ignore
        pass

    # The mail transport (app.core.email) opens its own SessionLocal to resolve
    # the active provider at send time. Point that at the test engine so a send
    # during a test uses the test DB, not the developer's dev database.
    import app.db.session as db_session

    original_session_local = db_session.SessionLocal
    db_session.SessionLocal = TestSessionLocal
    try:
        yield
    finally:
        db_session.SessionLocal = original_session_local


@pytest.fixture(autouse=True)
def _no_external_email(monkeypatch):
    """Never touch a real mail provider during integration tests.

    The dev ``.env`` may set ``SMTP_HOST`` / ``RESEND_API_KEY``, which would make
    ``settings.email_enabled`` true and send real email. Blank those so mail is
    treated as disabled (deterministic dev-mode: endpoints hand tokens back
    instead of emailing), and stub the transport dispatch so no network call is
    possible even when a test configures a provider in the DB. Tests that want to
    assert a send still mock ``app.core.email.send_email`` themselves.
    """
    from app.core.config import settings as app_settings

    for name in (
        "SMTP_HOST",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "RESEND_API_KEY",
        "RESEND_FROM_EMAIL",
    ):
        monkeypatch.setattr(app_settings, name, "", raising=False)

    import app.core.email as email_module

    monkeypatch.setattr(email_module, "_dispatch", lambda *args, **kwargs: True)


@pytest.fixture
def db():
    """Provide a transactional database session that rolls back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    """HTTP test client with database dependency override."""
    from fastapi.testclient import TestClient

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
