"""A seat held until its receipt is paid.

A pay-to-confirm seat is a registration today and a space booking tomorrow
(#603). What happens to the seat when its receipt changes is decided here once,
keyed on what the receipt is linked to, and each domain supplies only what is
specific to it. The domains are imported inside the functions because they
build on this package.
"""

from sqlalchemy.orm import Session

from app.domains.billing.models import Receipt


def confirm_paid_seat(db: Session, receipt: Receipt) -> None:
    """Confirm the pending seat this receipt pays for, if it has one.

    A no-op for every receipt that is not linked to a seat, and for a seat that
    is not pending, which is every seat of a ``legacy`` activity.
    """
    if receipt.registration_id is not None:
        from app.domains.activities.registration_service import (
            confirm_pending_registration,
        )

        confirm_pending_registration(db, receipt.registration_id)
