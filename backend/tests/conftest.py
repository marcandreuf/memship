"""Shared test fixtures."""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

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
from app.domains.members.models import Member, MembershipType  # noqa: F401
from app.domains.audit.models import AuditLog  # noqa: F401

# Use test database
TEST_DATABASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)
test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """Create all tables once per test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


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
    from httpx import ASGITransport, AsyncClient
    from fastapi.testclient import TestClient

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
