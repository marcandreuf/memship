"""A seat held until paid cannot be held without a receipt to pay (#603).

A ``legacy`` seat keeps the old rule: the place stands and the club raises the
receipt by hand.
"""

from unittest.mock import patch

import pytest

from app.domains.activities.models import Registration
from app.domains.activities.registration_service import (
    RegistrationError,
    register_member,
)
from tests.integration.test_registration_billing import (
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)

BROKEN = "app.domains.billing.service.generate_activity_receipt"


class TestAReceiptThatCannotBeRaised:
    def test_fails_a_pending_registration(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow="pay_to_confirm")
        member = _member(db, membership_type, "rf1")

        with patch(BROKEN, side_effect=RuntimeError("no numbering series")):
            with pytest.raises(RegistrationError) as exc:
                register_member(db, activity, member, price.id)

        assert exc.value.detail["code"] == "seat_receipt_failed"

    def test_leaves_a_legacy_registration_standing(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow="legacy")
        member = _member(db, membership_type, "rf2")

        with patch(BROKEN, side_effect=RuntimeError("no numbering series")):
            registration = register_member(db, activity, member, price.id)

        assert registration.status == "confirmed"
        assert _receipts_for(db, registration) == []
        assert db.query(Registration).filter_by(id=registration.id).one()
