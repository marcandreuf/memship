"""Per-year document counters, allocated under a row lock.

Receipts and remittances each keep one ``{year, next_number}`` row per year
(``InvoiceSequence``, ``RemittanceSequence``). A number is drawn by locking that
row ``FOR UPDATE``, reading it, and bumping it in the same transaction, so two
callers allocating at once serialise on the row instead of both reading the
same value. ``COUNT(rows in year) + 1`` — what both used to do — has no such
guarantee and also moves backwards when a row is deactivated.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base


def next_yearly_number(db: Session, sequence_model: type[Base], year: int) -> int:
    """Allocate and return the next number for ``year``, bumping the counter.

    ``sequence_model`` is a mapped class with ``year`` (primary key) and
    ``next_number`` columns. The caller must hold any coarser lock it needs
    (the org row, for receipts) before calling, and always in the same order.
    """
    row = (
        db.query(sequence_model)
        .filter(sequence_model.year == year)
        .with_for_update()
        .first()
    )
    if row is None:
        # First document of this year. Two callers can reach this at once, so
        # the loser of the insert re-reads the winner's row under the lock
        # rather than both starting at 1.
        try:
            with db.begin_nested():
                row = sequence_model(year=year, next_number=1)
                db.add(row)
                db.flush()
        except IntegrityError:
            row = (
                db.query(sequence_model)
                .filter(sequence_model.year == year)
                .with_for_update()
                .one()
            )
    number = row.next_number or 1
    row.next_number = number + 1
    return number
