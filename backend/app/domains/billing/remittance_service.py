"""Remittance service layer — batch creation, SEPA XML generation, return import."""

import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Query, Session, joinedload

from app.core.clock import org_today
from app.core.config import settings
from app.domains.billing.models import (
    Receipt,
    Remittance,
    RemittanceSequence,
    SepaMandate,
)
from app.domains.billing.schemas import (
    EligibleReceiptResponse,
    RemittanceCreate,
    ReturnEntry,
)
from app.domains.billing.sequences import next_yearly_number
from app.domains.billing.sepa_xml import SepaExportError, generate_sepa_xml
from app.domains.billing.service import mark_receipts_paid
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

logger = logging.getLogger(__name__)


def sepa_eligible_receipts_query(db: Session) -> Query:
    """The receipts a new SEPA remittance will accept.

    The same six conditions `create_remittance` enforces below, in one place
    the batch picker can ask about. The screen used to decide for itself and got
    three of them wrong: it ignored the document type, never checked for a
    mandate, and asked the API for `emitted` only — so every *overdue* receipt
    was unreachable from a dialog whose own text offers them, which is the set
    most in need of collection.
    """
    mandated = select(SepaMandate.member_id).filter(
        SepaMandate.status == "active",
        SepaMandate.is_active.is_(True),
    )
    return (
        db.query(Receipt)
        .filter(
            Receipt.is_active.is_(True),
            # A credit note moves money back to the member; it is not collected.
            Receipt.document_type == "invoice",
            Receipt.status.in_(("emitted", "overdue")),
            Receipt.is_batchable.is_(True),
            Receipt.remittance_id.is_(None),
            Receipt.member_id.in_(mandated),
            # A direct debit for zero collects nothing, and the bank file has no
            # way to express it — `sepaxml` fails on the empty amount with a bare
            # ValueError, which reached the admin as a 500 (#392). Zero is a
            # legitimate receipt total, so it is refused here rather than
            # forbidden outright.
            Receipt.total_amount > 0,
        )
        .options(joinedload(Receipt.member).joinedload(Member.person))
        .order_by(Receipt.due_date, Receipt.id)
    )


def label_members(db: Session, member_ids: list[int] | set[int]) -> list[str]:
    """Name members the way an admin can find them.

    An error that lists `[48]` is unresolvable from any screen — the member
    number and the name are what the register, the search box and the receipt
    all show.
    """
    rows = (
        db.query(Member.member_number, Person.first_name, Person.last_name)
        .join(Person, Member.person_id == Person.id)
        .filter(Member.id.in_(list(member_ids)))
        .all()
    )
    return sorted(
        " ".join(filter(None, [number, first, last])) for number, first, last in rows
    )


def describe_eligible_receipt(receipt: Receipt) -> dict:
    """A receipt for the batch picker, with the member it belongs to.

    Reads the `member` and `person` that `sepa_eligible_receipts_query` already
    eager-loads, so this adds no query — the identity was being fetched and
    then dropped by the response schema (#379).

    Composed the way `label_members` composes a refusal, so the picker and the
    error name the same member the same way.
    """
    member = receipt.member
    person = member.person if member is not None else None
    data = EligibleReceiptResponse.model_validate(receipt).model_dump()
    data["member_number"] = member.member_number if member is not None else None
    if person is not None:
        name = " ".join(filter(None, [person.first_name, person.last_name]))
        data["member_name"] = name or None
    else:
        data["member_name"] = None
    return data


# --- Remittance Number Generation ---


def generate_remittance_number(db: Session, emission_date: date) -> str:
    """Generate the next remittance number.

    Format: REM-{year}-{sequence:04d}, annual reset. Drawn from a per-year
    counter locked FOR UPDATE (see RemittanceSequence), the same way receipt
    numbers are — COUNT(remittances) + 1 let two concurrent generations pick
    the same number.
    """
    year = emission_date.year
    sequence = next_yearly_number(db, RemittanceSequence, year)
    number = f"REM-{year}-{sequence:04d}"

    # Under the lock a collision means the counter is behind the remittances
    # already issued — a number written outside this function — and stepping
    # past it would hide that. Surface it instead.
    if db.query(Remittance).filter(Remittance.remittance_number == number).first():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"Remittance number {number} already exists. The remittance "
                f"sequence for {year} is behind the remittances already issued "
                "and must be corrected before more are created."
            ),
        )

    return number


# --- Status Transitions ---

VALID_REMITTANCE_TRANSITIONS = {
    "draft": {"ready", "cancelled"},
    "ready": {"submitted", "cancelled"},
    # 'submitted' closes directly. A bank that has nothing to return sends
    # nothing, and import_returns — the only thing that sets 'processed' —
    # exists to record failures. Without this the batch where everyone paid is
    # the one that could never be closed, which is exactly the batch that most
    # needs reconciling.
    "submitted": {"processed", "closed"},
    "processed": {"closed"},
    "closed": set(),
    "cancelled": set(),
}


def validate_remittance_transition(current: str, target: str) -> None:
    """Validate that a remittance status transition is allowed."""
    allowed = VALID_REMITTANCE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition remittance from '{current}' to '{target}'",
        )


# --- CRUD ---


def create_remittance(
    db: Session, data: RemittanceCreate, created_by_id: int
) -> Remittance:
    """Create a remittance batch from a list of receipt IDs.

    Validates that all receipts are eligible (emitted/overdue, batchable,
    member has active mandate).
    """
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        raise HTTPException(status_code=500, detail="Organization settings not found")
    if not org.creditor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization creditor ID must be configured",
        )
    if not org.bank_iban:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization bank IBAN must be configured",
        )

    # Fetch receipts
    receipts = (
        db.query(Receipt)
        .filter(
            Receipt.id.in_(data.receipt_ids),
            Receipt.is_active.is_(True),
        )
        .all()
    )

    if len(receipts) != len(data.receipt_ids):
        found_ids = {r.id for r in receipts}
        missing = set(data.receipt_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Receipts not found: {sorted(missing)}",
        )

    # Validate each receipt
    errors = []
    member_ids = set()
    for r in receipts:
        if r.document_type != "invoice":
            errors.append(
                f"Receipt {r.receipt_number}: a credit note is not collected — "
                "the money moves back to the member"
            )
        if r.status not in ("emitted", "overdue"):
            errors.append(f"Receipt {r.receipt_number}: status '{r.status}' not eligible (must be emitted or overdue)")
        if not r.is_batchable:
            errors.append(f"Receipt {r.receipt_number}: not batchable")
        if r.remittance_id:
            errors.append(f"Receipt {r.receipt_number}: already in remittance #{r.remittance_id}")
        if Decimal(str(r.total_amount)) <= 0:
            errors.append(
                f"Receipt {r.receipt_number}: total is {r.total_amount} — a direct "
                "debit collects nothing and the bank file cannot express it"
            )
        member_ids.add(r.member_id)

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=errors,
        )

    # Check mandates for all members
    mandates = (
        db.query(SepaMandate)
        .filter(
            SepaMandate.member_id.in_(member_ids),
            SepaMandate.status == "active",
            SepaMandate.is_active.is_(True),
        )
        .all()
    )
    mandate_map = {}
    for m in mandates:
        # Keep the latest mandate per member
        if m.member_id not in mandate_map or m.created_at > mandate_map[m.member_id].created_at:
            mandate_map[m.member_id] = m

    members_without_mandate = member_ids - set(mandate_map.keys())
    if members_without_mandate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "members_without_mandate",
                "members": label_members(db, members_without_mandate),
            },
        )

    # Calculate total
    total = sum(Decimal(str(r.total_amount)) for r in receipts)

    # Create remittance
    today = org_today(db)
    remittance = Remittance(
        remittance_number=generate_remittance_number(db, today),
        remittance_type="sepa",
        status="draft",
        emission_date=today,
        due_date=data.due_date,
        total_amount=total,
        receipt_count=len(receipts),
        creditor_name=org.name,
        creditor_iban=org.bank_iban,
        creditor_bic=org.bank_bic,
        creditor_id=org.creditor_id,
        notes=data.notes,
        created_by=created_by_id,
    )
    db.add(remittance)
    db.flush()

    # Link receipts
    for r in receipts:
        r.remittance_id = remittance.id

    db.flush()
    return remittance


def generate_remittance_xml(db: Session, remittance: Remittance) -> bytes:
    """Generate SEPA XML for a remittance and save to storage.

    Transitions status to 'ready'.
    """
    if remittance.status not in ("draft", "ready"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot generate XML for remittance in '{remittance.status}' status",
        )

    receipts = (
        db.query(Receipt)
        .filter(Receipt.remittance_id == remittance.id, Receipt.is_active.is_(True))
        .order_by(Receipt.id)
        .all()
    )
    if not receipts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Remittance has no receipts",
        )

    # The batch's own numbers against what it actually holds. Everything that
    # takes a receipt out of an open batch recounts it, so this cannot fire in
    # normal operation — it is here because the file is the thing the bank acts
    # on, and a future path that forgets to recount must not be able to produce
    # one that collects less than the batch says (#384). `SepaExportError`
    # already refuses for a vanished mandate; this is the same refusal for a
    # vanished receipt.
    live_total = sum(
        (Decimal(str(r.total_amount)) for r in receipts), Decimal("0")
    )
    stored_total = Decimal(str(remittance.total_amount))
    if len(receipts) != remittance.receipt_count or live_total != stored_total:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "remittance_out_of_step",
                "remittance_number": remittance.remittance_number,
                "stored_count": remittance.receipt_count,
                "stored_total": str(stored_total),
                "live_count": len(receipts),
                "live_total": str(live_total),
            },
        )

    # Load mandates
    member_ids = {r.member_id for r in receipts}
    mandates = (
        db.query(SepaMandate)
        .filter(
            SepaMandate.member_id.in_(member_ids),
            SepaMandate.status == "active",
            SepaMandate.is_active.is_(True),
        )
        .all()
    )
    mandate_map = {}
    for m in mandates:
        if m.member_id not in mandate_map or m.created_at > mandate_map[m.member_id].created_at:
            mandate_map[m.member_id] = m

    # A batch created before the eligibility gate existed can still hold a
    # 0,00 € receipt (#392). Name it here rather than let `sepaxml` fail on the
    # empty amount, because its ValueError says nothing about which receipt.
    without_amount = [r for r in receipts if Decimal(str(r.total_amount)) <= 0]
    if without_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "receipts_without_amount",
                "remittance_number": remittance.remittance_number,
                "receipts": [r.receipt_number for r in without_amount],
            },
        )

    # Generate XML. Mandates are re-read above, so one cancelled between
    # create_remittance and now is missing here even though creation checked for
    # it. Refuse rather than write a file that collects less than the remittance
    # says it does — see SepaExportError.
    try:
        xml_bytes = generate_sepa_xml(remittance, receipts, mandate_map)
    except SepaExportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "sepa_mandate_cancelled",
                "members": label_members(db, exc.member_ids),
                "message": str(exc),
            },
        ) from exc
    except Exception as exc:
        # `SepaExportError` covers what memship anticipates. Everything else out
        # of `sepaxml` is a library-level failure that used to surface as a bare
        # 500 with no message (#392): log the cause, and leave the admin the
        # remittance number to report.
        logger.exception(
            "SEPA file generation failed for remittance %s",
            remittance.remittance_number,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "sepa_file_build_failed",
                "remittance_number": remittance.remittance_number,
            },
        ) from exc

    # Save to storage
    year = remittance.emission_date.year
    storage_dir = Path(settings.STORAGE_LOCAL_PATH) / "remittances" / str(year)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / f"{remittance.remittance_number}.xml"
    with open(file_path, "wb") as f:
        f.write(xml_bytes)

    remittance.sepa_file_path = str(file_path)
    remittance.status = "ready"
    db.flush()

    return xml_bytes


def mark_submitted(db: Session, remittance: Remittance) -> Remittance:
    """Mark remittance as submitted to bank."""
    validate_remittance_transition(remittance.status, "submitted")
    remittance.status = "submitted"
    db.flush()
    return remittance


# The only statuses a return can act on. A receipt in any other status is
# reported rather than changed — and `paid` refuses the import outright, see
# below.
RETURNABLE_STATUSES = ("emitted", "overdue")

DEFAULT_RETURN_REASON = "Returned by bank"


def import_returns(
    db: Session, remittance: Remittance, return_data: list[ReturnEntry]
) -> dict:
    """Process return/rejection data for a remittance.

    Reports what *happened* to each entry rather than how many of them were
    recognised, and names the receipts in every bucket: the summary is the only
    feedback the screen gives, and `processed` used to count every matched
    receipt whether or not anything changed — so a return landing on a receipt
    that was already paid read as handled and silently did nothing (#391).

    A return against a `paid` receipt refuses the whole import. The bank is
    saying it took the money back while memship is saying it collected it, and
    that is a contradiction for someone to resolve rather than a line in a
    summary — the same refuse-and-name shape `create_remittance` uses for a
    member without a mandate. It is reachable without anything exotic: a member
    paying by card while the direct debit is in flight has the provider webhook
    mark the receipt paid, and webhooks are deliberately exempt from the
    in-flight guard in `refuse_if_collection_in_flight` (#383), because a
    webhook means the money really did move.

    Returns the receipt numbers in each bucket: `returned`, `already_returned`,
    `ignored` (matched, but in a status a return cannot act on), `duplicate`,
    `not_in_batch` (the number exists, but belongs to another batch or none) and
    `not_found`.
    """
    if remittance.status not in ("submitted", "processed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot import returns for remittance in '{remittance.status}' status",
        )

    receipts = (
        db.query(Receipt)
        .filter(Receipt.remittance_id == remittance.id, Receipt.is_active.is_(True))
        .all()
    )
    receipt_map = {r.receipt_number: r for r in receipts}

    # Numbers this batch does not hold. Reporting them all as "not found"
    # implied they were unknown; most are real receipts that are simply
    # somewhere else, and saying where is the more useful answer.
    unmatched = {e.receipt_number for e in return_data} - receipt_map.keys()
    elsewhere = {}
    if unmatched:
        elsewhere = {
            r.receipt_number: r.remittance.remittance_number if r.remittance else None
            for r in db.query(Receipt)
            .filter(Receipt.receipt_number.in_(unmatched))
            .options(joinedload(Receipt.remittance))
            .all()
        }

    # Refuse before writing anything, so the import is all-or-nothing.
    conflicting = sorted(
        {
            e.receipt_number
            for e in return_data
            if e.receipt_number in receipt_map
            and receipt_map[e.receipt_number].status == "paid"
        }
    )
    if conflicting:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "return_against_paid_receipt",
                "remittance_number": remittance.remittance_number,
                "receipts": conflicting,
            },
        )

    returned: list[str] = []
    already_returned: list[str] = []
    ignored: list[dict] = []
    duplicate: list[str] = []
    not_in_batch: list[dict] = []
    not_found: list[str] = []
    seen: set[str] = set()

    for entry in return_data:
        number = entry.receipt_number
        if number in seen:
            duplicate.append(number)
            continue
        seen.add(number)

        receipt = receipt_map.get(number)
        if receipt is None:
            if number in elsewhere:
                not_in_batch.append(
                    {"receipt_number": number, "remittance_number": elsewhere[number]}
                )
            else:
                not_found.append(number)
            continue

        if receipt.status == "returned":
            already_returned.append(number)
            continue
        if receipt.status not in RETURNABLE_STATUSES:
            ignored.append({"receipt_number": number, "status": receipt.status})
            continue

        receipt.status = "returned"
        receipt.return_reason = (entry.reason or DEFAULT_RETURN_REASON)[:255]
        receipt.return_date = org_today(db)
        returned.append(number)

    if remittance.status == "submitted":
        remittance.status = "processed"

    db.flush()
    return {
        "returned": returned,
        "already_returned": already_returned,
        "ignored": ignored,
        "duplicate": duplicate,
        "not_in_batch": not_in_batch,
        "not_found": not_found,
    }


# Statuses a receipt is left in while its collection is still in flight. Anything
# else in the batch has already been settled by hand or reported back by the bank.
AWAITING_SETTLEMENT = ("emitted", "overdue")


def close_remittance(db: Session, remittance: Remittance) -> tuple[Remittance, list[int]]:
    """Close a remittance — the settlement window has passed, so reconcile it.

    SEPA confirms nothing. The bank reports the collections that failed and says
    nothing at all about the rest, so closing is a human asserting that the
    window has passed: every receipt still awaiting settlement is taken as
    collected and marked paid. Receipts ``import_returns`` already flipped to
    'returned', and cancelled or deactivated ones, are left alone.

    The payment date is the remittance's own due date — the SEPA collection
    date, when the money actually moved — rather than the moment the admin got
    round to finishing the batch, which would book a March collection in April.

    The whole batch is marked in the caller's transaction, so a remittance can
    never end up 'closed' with some of its receipts still awaiting settlement.
    Returns the remittance and the receipts owed a payment notification, for the
    caller to dispatch once it has committed.
    """
    validate_remittance_transition(remittance.status, "closed")

    receipts = (
        db.query(Receipt)
        .filter(
            Receipt.remittance_id == remittance.id,
            Receipt.is_active.is_(True),
            Receipt.status.in_(AWAITING_SETTLEMENT),
        )
        .order_by(Receipt.id)
        .all()
    )
    pending = mark_receipts_paid(
        db,
        receipts,
        payment_method="direct_debit",
        payment_date=remittance.due_date,
    )

    remittance.status = "closed"
    db.flush()
    return remittance, pending


def cancel_remittance(db: Session, remittance: Remittance) -> Remittance:
    """Cancel a remittance — unlink all receipts."""
    validate_remittance_transition(remittance.status, "cancelled")

    receipts = (
        db.query(Receipt)
        .filter(Receipt.remittance_id == remittance.id)
        .all()
    )
    for r in receipts:
        r.remittance_id = None

    remittance.status = "cancelled"
    db.flush()
    return remittance
