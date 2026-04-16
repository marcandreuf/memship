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
from app.domains.auth.models import User  # noqa: F401
from app.domains.members.models import Group, Member, MembershipType  # noqa: F401
from app.domains.audit.models import AuditLog  # noqa: F401
from app.domains.activities.models import (  # noqa: F401
    Activity, ActivityAttachmentType, ActivityConsent, ActivityModality,
    ActivityPrice, DiscountCode, Registration, RegistrationAttachment,
    RegistrationConsent,
)
from app.domains.billing.models import (  # noqa: F401
    Concept, PaymentProvider, Receipt, Remittance, SepaMandate, WebhookEvent,
)

# Use test database
TEST_DATABASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)
test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """Create all tables once per test session.

    With pytest-xdist, multiple workers may call this concurrently.
    create_all uses IF NOT EXISTS for most DDL, but PostgreSQL type
    creation can race. We catch and ignore that specific error.
    Skips drop_all — the test DB is ephemeral (CI service or local docker).
    """
    from sqlalchemy.exc import IntegrityError

    try:
        Base.metadata.create_all(bind=test_engine)
    except IntegrityError:
        # Another xdist worker already created the tables — safe to ignore
        pass

    yield


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
