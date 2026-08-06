"""Evidence that v1.4.0 is invisible.

The permission layer replaced an ordinal ladder. These tests assert the reach of
each legacy role shape is unchanged, and that nothing of the old mechanism
survives in the tree.
"""

import re
from pathlib import Path

import pytest

from app.core.authorization import resolve_permissions
from app.core.permissions import ALL_KEYS, MEMBER_SEED_KEYS, RESERVED_KEYS
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.persons.models import Person
from app.domains.reports.schemas import AnnualSummary

APP = Path(__file__).resolve().parents[2] / "app"


def _user(db, email, role):
    person = Person(first_name=role, last_name="Parity", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=email,
        password_hash=hash_password("password123"), role=role, is_active=True,
    )
    db.add(user)
    db.flush()
    return user


class TestLegacyRoleParity:
    """What each pre-v1.4 role could reach, it still reaches — no more, no less."""

    def test_super_admin_reaches_everything(self, db):
        user = _user(db, "parity-super@test.com", "super_admin")

        assert resolve_permissions(user) == ALL_KEYS

    def test_admin_reaches_everything_except_the_super_admin_only_keys(self, db):
        user = _user(db, "parity-admin@test.com", "admin")

        held = resolve_permissions(user)

        assert not (held & RESERVED_KEYS)
        assert "settings.custom_fields.write" not in held
        assert held == ALL_KEYS - RESERVED_KEYS - {"settings.custom_fields.write"}

    def test_member_reaches_only_self_service(self, db):
        user = _user(db, "parity-member@test.com", "member")

        assert resolve_permissions(user) == set(MEMBER_SEED_KEYS)

    def test_restricted_lands_on_member_with_no_staff_reach(self, db):
        """The tier is gone; a hand-provisioned account backfills to `member`.
        Its two real capabilities — everyone's custom-field values, cancel any
        booking — are deliberately lost."""
        user = _user(db, "parity-restricted@test.com", "restricted")

        held = resolve_permissions(user)

        assert held == set(MEMBER_SEED_KEYS)
        assert "members.read" not in held
        assert "bookings.write" not in held

    def test_every_shape_holds_the_self_namespace(self, db):
        for i, role in enumerate(("super_admin", "admin", "member")):
            user = _user(db, f"parity-self-{i}@test.com", role)

            assert set(MEMBER_SEED_KEYS) <= resolve_permissions(user)


class TestNoOrdinalLadderSurvives:
    """A grep-style guard: the old mechanism must not creep back."""

    @pytest.mark.parametrize(
        "pattern",
        ["ROLE_HIERARCHY", r"\brequire_admin\b", r"\brequire_super_admin\b"],
    )
    def test_symbol_is_gone_from_the_tree(self, pattern):
        offenders = [
            f"{path.relative_to(APP)}"
            for path in APP.rglob("*.py")
            if re.search(pattern, path.read_text(encoding="utf8"))
        ]

        assert offenders == []

    def test_no_code_reads_a_role_string_off_the_user(self):
        """``users.role`` is dropped; a survivor would be an AttributeError in
        production and is invisible until that route is hit."""
        offenders = []
        for path in APP.rglob("*.py"):
            for n, line in enumerate(path.read_text(encoding="utf8").split("\n"), 1):
                if re.search(r"current_user\.role\b|\buser\.role\b", line):
                    offenders.append(f"{path.relative_to(APP)}:{n}")

        assert offenders == []


class TestAnnualSummaryStaysAggregateOnly:
    """`reports.read` is justified only while this payload names nobody.

    It grants whole-club totals to a board member who cannot open a single
    member record. The moment an identity appears here, that grant becomes a
    hole and the key needs re-deriving.
    """

    IDENTITY_HINTS = ("name", "email", "id", "member", "person", "iban", "phone")

    def test_no_field_carries_an_identity(self):
        offenders = [
            field
            for field in AnnualSummary.model_fields
            if field != "year"
            and any(hint in field.lower() for hint in self.IDENTITY_HINTS)
            and not field.endswith(("_by_month", "_members", "_growth"))
        ]

        assert offenders == []

    def test_every_field_is_a_count_a_sum_or_a_breakdown(self):
        for field, info in AnnualSummary.model_fields.items():
            annotation = str(info.annotation)

            assert any(
                token in annotation
                for token in ("int", "float", "Decimal", "ActivityParticipation")
            ), f"{field}: {annotation}"

    def test_activity_participation_carries_no_identity(self):
        from app.domains.reports.schemas import ActivityParticipation

        assert set(ActivityParticipation.model_fields) == {"activity_name", "count"}