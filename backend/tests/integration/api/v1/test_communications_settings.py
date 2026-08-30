"""Tests for the superadmin communications configuration screen.

Covers the three tiers (mandatory templates always send and cannot be switched
off), the default-off resolution for an untouched install, the gate applied at
send time in ``app.core.email``, and the masked GET / sparse PUT endpoints.
"""

from unittest.mock import patch

from app.core import email as email_module
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.audit.models import AuditLog
from app.domains.auth.models import User
from app.domains.mailing.policy import (
    CATALOG,
    MANDATORY,
    enabled_map,
    is_enabled,
)
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Test Club")
        db.add(org)
        db.flush()
    org.communications_config = {}
    db.flush()
    return org


def _create_user(db, role="super_admin", suffix="comms"):
    email = f"{suffix}-{role}@example4f1c2a.com"
    person = Person(first_name="T", last_name="U", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


class TestCatalog:
    def test_mandatory_is_exactly_the_account_access_templates(self):
        assert MANDATORY == frozenset({"verification", "password_reset"})

    def test_every_key_is_unique_and_has_a_group(self):
        keys = [spec.key for spec in CATALOG]
        assert len(keys) == len(set(keys))
        assert all(spec.group for spec in CATALOG)

    def test_mailing_test_is_not_configurable(self):
        """The settings screen's own credential check is not a member email."""
        assert "mailing_test" not in {spec.key for spec in CATALOG}


class TestResolution:
    def test_untouched_install_sends_only_the_mandatory_templates(self, db):
        """Nothing optional leaves a fresh install until someone opts in."""
        _org(db)
        resolved = enabled_map(db)
        assert set(resolved) == {spec.key for spec in CATALOG}
        assert {key for key, on in resolved.items() if on} == MANDATORY

    def test_enabled_key_resolves_true(self, db):
        org = _org(db)
        org.communications_config = {"templates": {"booking_confirmation": {"enabled": True}}}
        db.flush()

        assert is_enabled(db, "booking_confirmation") is True
        # Untouched siblings stay off — enabling one is not enabling the group.
        assert is_enabled(db, "booking_promoted") is False

    def test_explicit_false_resolves_false(self, db):
        org = _org(db)
        org.communications_config = {"templates": {"booking_confirmation": {"enabled": False}}}
        db.flush()

        assert is_enabled(db, "booking_confirmation") is False

    def test_mandatory_ignores_a_stored_false(self, db):
        """Even if a row is written directly, a mandatory template still sends."""
        org = _org(db)
        org.communications_config = {"templates": {"password_reset": {"enabled": False}}}
        db.flush()

        assert is_enabled(db, "password_reset") is True
        assert enabled_map(db)["password_reset"] is True

    def test_unknown_key_sends(self, db):
        _org(db)
        assert is_enabled(db, "not_a_template") is True


class TestSendGate:
    """The gate lives in ``_send_templated``, so every sender honours it."""

    @patch("app.core.email.send_email", return_value=True)
    @patch("app.core.email._template_enabled", return_value=False)
    def test_disabled_template_is_not_sent(self, _gate, mock_send):
        ok = email_module.send_booking_confirmation_email(
            "m@example.com", "Ana", "Court 1", "01/09/2026", "10:00"
        )
        assert ok is False
        mock_send.assert_not_called()

    @patch("app.core.email.send_email", return_value=True)
    @patch("app.core.email._template_enabled", return_value=True)
    def test_enabled_template_is_sent(self, _gate, mock_send):
        ok = email_module.send_booking_confirmation_email(
            "m@example.com", "Ana", "Court 1", "01/09/2026", "10:00"
        )
        assert ok is True
        mock_send.assert_called_once()

    @patch("app.core.email.send_email", return_value=True)
    def test_gate_failure_sends_anyway(self, mock_send):
        """A broken policy lookup must not silently suppress mail."""
        with patch(
            "app.core.email.is_template_enabled", side_effect=RuntimeError("db down")
        ):
            ok = email_module.send_booking_confirmation_email(
                "m@example.com", "Ana", "Court 1", "01/09/2026", "10:00"
            )
        assert ok is True
        mock_send.assert_called_once()

    @patch("app.core.email.send_email", return_value=True)
    def test_mandatory_template_sends_when_disabled_in_db(self, mock_send, db):
        org = _org(db)
        org.communications_config = {"templates": {"verification": {"enabled": False}}}
        db.commit()

        assert email_module.send_verification_email(
            "u@example.com", "Ana", "https://example.com/verify?t=x"
        ) is True
        mock_send.assert_called_once()


class TestEndpoints:
    def test_requires_superadmin(self, client, db):
        member = _create_user(db, role="member", suffix="comms-rbac")
        db.commit()
        client.cookies.update(_auth_cookie(member))
        assert client.get("/api/v1/settings/communications").status_code == 403

    def test_get_lists_every_template_with_tier(self, client, db):
        _org(db)
        admin = _create_user(db, suffix="comms-get")
        db.commit()
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/settings/communications")
        assert resp.status_code == 200
        templates = resp.json()["templates"]
        assert len(templates) == len(CATALOG)

        by_key = {t["key"]: t for t in templates}
        assert by_key["password_reset"]["tier"] == "mandatory"
        assert by_key["receipt_delivery"]["tier"] == "operational"
        assert by_key["announcement"]["tier"] == "optional"
        assert {t["key"] for t in templates if t["enabled"]} == MANDATORY

    def test_put_enables_a_template(self, client, db):
        _org(db)
        admin = _create_user(db, suffix="comms-put")
        db.commit()
        client.cookies.update(_auth_cookie(admin))

        resp = client.put(
            "/api/v1/settings/communications",
            json={"templates": {"booking_confirmation": True}},
        )
        assert resp.status_code == 200
        by_key = {t["key"]: t for t in resp.json()["templates"]}
        assert by_key["booking_confirmation"]["enabled"] is True
        assert by_key["booking_waitlisted"]["enabled"] is False

        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        db.refresh(org)
        assert org.communications_config["templates"]["booking_confirmation"]["enabled"] is True

    def test_put_disables_a_template(self, client, db):
        org = _org(db)
        org.communications_config = {"templates": {"booking_confirmation": {"enabled": True}}}
        db.flush()
        admin = _create_user(db, suffix="comms-put-off")
        db.commit()
        client.cookies.update(_auth_cookie(admin))

        resp = client.put(
            "/api/v1/settings/communications",
            json={"templates": {"booking_confirmation": False}},
        )
        assert resp.status_code == 200
        by_key = {t["key"]: t for t in resp.json()["templates"]}
        assert by_key["booking_confirmation"]["enabled"] is False

        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        db.refresh(org)
        assert org.communications_config["templates"]["booking_confirmation"]["enabled"] is False

    def test_put_is_sparse(self, client, db):
        org = _org(db)
        org.communications_config = {"templates": {"announcement": {"enabled": True}}}
        db.flush()
        admin = _create_user(db, suffix="comms-sparse")
        db.commit()
        client.cookies.update(_auth_cookie(admin))

        resp = client.put(
            "/api/v1/settings/communications",
            json={"templates": {"billing_summary": True}},
        )
        by_key = {t["key"]: t for t in resp.json()["templates"]}
        assert by_key["announcement"]["enabled"] is True
        assert by_key["billing_summary"]["enabled"] is True

    def test_put_rejects_disabling_a_mandatory_template(self, client, db):
        _org(db)
        admin = _create_user(db, suffix="comms-mand")
        db.commit()
        client.cookies.update(_auth_cookie(admin))

        resp = client.put(
            "/api/v1/settings/communications",
            json={"templates": {"password_reset": False}},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "template_mandatory"

    def test_put_accepts_enabling_a_mandatory_template_as_a_no_op(self, client, db):
        _org(db)
        admin = _create_user(db, suffix="comms-mand-on")
        db.commit()
        client.cookies.update(_auth_cookie(admin))

        resp = client.put(
            "/api/v1/settings/communications",
            json={"templates": {"password_reset": True}},
        )
        assert resp.status_code == 200
        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        db.refresh(org)
        assert "password_reset" not in (org.communications_config.get("templates") or {})

    def test_put_rejects_an_unknown_key(self, client, db):
        _org(db)
        admin = _create_user(db, suffix="comms-unknown")
        db.commit()
        client.cookies.update(_auth_cookie(admin))

        resp = client.put(
            "/api/v1/settings/communications",
            json={"templates": {"not_a_template": False}},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "unknown_template"

    def test_change_is_audited(self, client, db):
        _org(db)
        admin = _create_user(db, suffix="comms-audit")
        db.commit()
        client.cookies.update(_auth_cookie(admin))

        client.put(
            "/api/v1/settings/communications",
            json={"templates": {"registration_rejected": True}},
        )

        entry = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "organization_settings")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert entry is not None
        assert "communications_config.registration_rejected" in entry.changed_fields

    def test_unchanged_put_writes_no_audit_row(self, client, db):
        """Switching off what is already off by default changes nothing."""
        _org(db)
        admin = _create_user(db, suffix="comms-noop")
        db.commit()
        client.cookies.update(_auth_cookie(admin))

        before = db.query(AuditLog).filter(
            AuditLog.table_name == "organization_settings"
        ).count()
        client.put(
            "/api/v1/settings/communications",
            json={"templates": {"announcement": False}},
        )
        after = db.query(AuditLog).filter(
            AuditLog.table_name == "organization_settings"
        ).count()
        assert after == before
