"""Releasing a seat voids its unpaid invoices the way cancelling a receipt does.

Shared by registrations and bookings (#603). Two things the shortcut that set
``status = 'cancelled'`` by hand got wrong: it cancelled credit notes, which carry
their invoice's link and are final, and it left a voided receipt in a remittance
still being assembled, which the file would then collect anyway (#383).
"""

from datetime import date
from decimal import Decimal

from app.domains.activities.registration_service import (
    cancel_registration,
    register_member,
)
from app.domains.billing.models import Remittance
from app.domains.billing.schemas import CreditNoteCreate
from app.domains.billing.service import create_credit_note
from tests.integration.test_registration_billing import (
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)


def _registered(db, membership_type, suffix):
    activity, price = _activity(db)
    registration = register_member(
        db, activity, _member(db, membership_type, suffix), price.id
    )
    [receipt] = _receipts_for(db, registration)
    return registration, receipt


def _open_batch(db, receipt):
    batch = Remittance(
        remittance_number=f"REM-{receipt.id}",
        status="draft",
        emission_date=date.today(),
        due_date=date.today(),
        total_amount=receipt.total_amount,
        receipt_count=1,
        creditor_name="Club",
        creditor_iban="ES9121000418450200051332",
        creditor_id="ES12ZZZ12345678",
    )
    db.add(batch)
    db.flush()
    receipt.remittance_id = batch.id
    db.flush()
    return batch


class TestReleasingASeat:
    def test_leaves_a_credit_note_alone(self, db, org, membership_type):
        registration, receipt = _registered(db, membership_type, "void-cn")
        note = create_credit_note(
            db, receipt, CreditNoteCreate(reason="Discount", amount=Decimal("1")), None
        )

        cancel_registration(db, registration)

        assert receipt.status == "cancelled"
        assert note.status == "emitted"

    def test_takes_the_receipt_out_of_a_batch_not_yet_sent(
        self, db, org, membership_type
    ):
        registration, receipt = _registered(db, membership_type, "void-batch")
        batch = _open_batch(db, receipt)

        cancel_registration(db, registration)

        assert receipt.status == "cancelled"
        assert receipt.remittance_id is None
        db.refresh(batch)
        assert batch.receipt_count == 0
