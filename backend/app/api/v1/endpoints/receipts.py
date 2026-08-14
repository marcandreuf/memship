"""Receipt management endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.core.authorization import require_permission, user_has
from app.core.csv_export import stream_csv
from app.core.pagination import paginate
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.billing.models import Receipt, ReceiptReminder
from app.domains.billing.reminder_service import send_reminder
from app.domains.billing.schemas import (
    GenerateMembershipFeesRequest,
    ReceiptCreate,
    ReceiptDetailResponse,
    ReceiptPayRequest,
    ReceiptReminderResponse,
    ReceiptResponse,
    ReceiptReturnRequest,
    ReceiptUpdate,
)
from app.domains.billing.service import (
    build_receipts_query,
    cancel_receipt,
    create_receipt,
    emit_receipt,
    generate_membership_fees,
    pay_receipt,
    reemit_receipt,
    return_receipt,
    update_receipt,
)
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

router = APIRouter(prefix="/receipts", tags=["receipts"])
member_router = APIRouter(tags=["receipts"])


def _own_member(db: Session, user: User) -> Member | None:
    """Resolve the caller's member record through the foreign key.

    Never through ``Person.email``: that column carries a non-unique index and a
    minor routinely shares their guardian's address, so an email match can
    return somebody else's member row — and every "own receipts only" check in
    this module then compares against the wrong member id.
    """
    return (
        db.query(Member)
        .filter(Member.user_id == user.id, Member.is_active.is_(True))
        .first()
    )


def _require_own_receipt(
    db: Session, user: User, receipt: Receipt, staff_permission: str
) -> None:
    """Allow staff holding ``staff_permission``, otherwise the receipt's owner.

    ``staff_permission`` is ``billing.read`` for the routes that only disclose a
    receipt and ``billing.write`` for the ones that start a payment against it —
    a view-only billing role must not be able to charge an arbitrary member.
    """
    if user_has(user, staff_permission):
        return
    member = _own_member(db, user)
    if not member or receipt.member_id != member.id:
        raise HTTPException(status_code=403, detail="Access denied")


def _to_detail(receipt: Receipt) -> dict:
    """Convert a Receipt to a detail response dict with member/concept names."""
    data = {c.name: getattr(receipt, c.name) for c in receipt.__table__.columns}
    data["member_name"] = None
    data["member_number"] = None
    data["concept_name"] = None
    if receipt.member and receipt.member.person:
        p = receipt.member.person
        data["member_name"] = f"{p.first_name} {p.last_name}"
        data["member_number"] = receipt.member.member_number
    if receipt.concept:
        data["concept_name"] = receipt.concept.name
    return data


@router.get("/")
def list_receipts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    origin: str | None = Query(None),
    member_id: int | None = Query(None),
    search: str | None = Query(None),
    emission_date_from: date | None = Query(None),
    emission_date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.read")),
):
    """List receipts with filters (admin only)."""
    query = build_receipts_query(
        db,
        status=status_filter,
        origin=origin,
        member_id=member_id,
        search=search,
        emission_date_from=emission_date_from,
        emission_date_to=emission_date_to,
    )
    items, meta = paginate(query, page, per_page)

    return {
        "items": [_to_detail(r) for r in items],
        "meta": meta.model_dump(),
    }


_RECEIPTS_CSV_HEADERS = [
    "receipt_number",
    "member_number",
    "member_name",
    "concept",
    "origin",
    "status",
    "base_amount",
    "vat_amount",
    "total_amount",
    "emission_date",
    "due_date",
    "payment_date",
]


def _receipt_csv_row(receipt: Receipt) -> list:
    member_name = None
    member_number = None
    if receipt.member and receipt.member.person:
        p = receipt.member.person
        member_name = f"{p.first_name} {p.last_name}"
        member_number = receipt.member.member_number
    return [
        receipt.receipt_number,
        member_number,
        member_name,
        receipt.concept.name if receipt.concept else None,
        receipt.origin,
        receipt.status,
        receipt.base_amount,
        receipt.vat_amount,
        receipt.total_amount,
        receipt.emission_date,
        receipt.due_date,
        receipt.payment_date,
    ]


@router.get("/export.csv")
def export_receipts_csv(
    status_filter: str | None = Query(None, alias="status"),
    origin: str | None = Query(None),
    member_id: int | None = Query(None),
    search: str | None = Query(None),
    emission_date_from: date | None = Query(None),
    emission_date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.read")),
):
    """Export receipts as CSV, honouring the same filters as the list endpoint."""
    query = build_receipts_query(
        db,
        status=status_filter,
        origin=origin,
        member_id=member_id,
        search=search,
        emission_date_from=emission_date_from,
        emission_date_to=emission_date_to,
    )
    rows = (_receipt_csv_row(r) for r in query.yield_per(500))
    return stream_csv(_RECEIPTS_CSV_HEADERS, rows, "receipts.csv")


@router.get("/stats")
def receipt_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.read")),
):
    """Receipt stats for admin dashboard."""
    from sqlalchemy import func as sqlfunc, extract
    from app.domains.billing.models import Receipt as R

    # Status counts
    status_counts = (
        db.query(R.status, sqlfunc.count(R.id))
        .filter(R.is_active.is_(True))
        .group_by(R.status)
        .all()
    )
    statuses = {s: c for s, c in status_counts}

    # Total amounts
    today = date.today()
    pending_amount = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(R.total_amount), 0))
        .filter(R.is_active.is_(True), R.status.in_(["pending", "emitted", "overdue"]))
        .scalar()
    )
    paid_this_month = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(R.total_amount), 0))
        .filter(
            R.is_active.is_(True),
            R.status == "paid",
            extract("year", R.payment_date) == today.year,
            extract("month", R.payment_date) == today.month,
        )
        .scalar()
    )
    overdue_amount = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(R.total_amount), 0))
        .filter(R.is_active.is_(True), R.status == "overdue")
        .scalar()
    )

    return {
        "new": statuses.get("new", 0),
        "pending": statuses.get("pending", 0),
        "emitted": statuses.get("emitted", 0),
        "paid": statuses.get("paid", 0),
        "returned": statuses.get("returned", 0),
        "cancelled": statuses.get("cancelled", 0),
        "overdue": statuses.get("overdue", 0),
        "pending_amount": float(pending_amount),
        "paid_this_month": float(paid_this_month),
        "overdue_amount": float(overdue_amount),
    }


@router.get("/{receipt_id}", response_model=ReceiptDetailResponse)
def get_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.read")),
):
    """Get a single receipt detail."""
    receipt = (
        db.query(Receipt)
        .filter(Receipt.id == receipt_id, Receipt.is_active.is_(True))
        .options(
            joinedload(Receipt.member).joinedload(Member.person),
            joinedload(Receipt.concept),
        )
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return _to_detail(receipt)


@router.get("/{receipt_id}/pdf")
def download_receipt_pdf(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.billing.read")),
):
    """Download a receipt as PDF. Admin can download any, member can download own."""
    receipt = (
        db.query(Receipt)
        .filter(Receipt.id == receipt_id, Receipt.is_active.is_(True))
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Members can only download their own receipts
    _require_own_receipt(db, current_user, receipt, "billing.read")

    from app.domains.billing.pdf import generate_receipt_pdf

    pdf_bytes = generate_receipt_pdf(db, receipt)
    filename = f"{receipt.receipt_number}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
def create_receipt_endpoint(
    data: ReceiptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.write")),
):
    """Create a manual receipt."""
    # Validate member exists
    member = db.query(Member).filter(Member.id == data.member_id).first()
    if not member:
        raise HTTPException(status_code=400, detail="Member not found")

    receipt = create_receipt(db, data, current_user.id)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.put("/{receipt_id}", response_model=ReceiptResponse)
def update_receipt_endpoint(
    receipt_id: int,
    data: ReceiptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.write")),
):
    """Update a receipt (only in new/pending status)."""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id, Receipt.is_active.is_(True)
    ).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    receipt = update_receipt(db, receipt, data)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.post("/{receipt_id}/emit", response_model=ReceiptResponse)
def emit_receipt_endpoint(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.write")),
):
    """Emit a receipt — assign number and send to member."""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id, Receipt.is_active.is_(True)
    ).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    receipt = emit_receipt(db, receipt)
    db.commit()
    db.refresh(receipt)

    # Send receipt PDF by email asynchronously
    try:
        from app.tasks.email_tasks import send_receipt_email_task
        send_receipt_email_task.delay(receipt.id)
    except Exception:
        pass  # Don't fail the emit if email dispatch fails

    return receipt


@router.post("/{receipt_id}/pay", response_model=ReceiptResponse)
def pay_receipt_endpoint(
    receipt_id: int,
    data: ReceiptPayRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.write")),
):
    """Mark a receipt as paid."""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id, Receipt.is_active.is_(True)
    ).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    receipt = pay_receipt(db, receipt, data)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.post("/{receipt_id}/send-reminder", response_model=ReceiptReminderResponse)
def send_receipt_reminder(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.write")),
):
    """Manually send a payment reminder for an unpaid (emitted/overdue) receipt."""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id, Receipt.is_active.is_(True)
    ).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt.status not in ("emitted", "overdue"):
        raise HTTPException(
            status_code=409, detail="Receipt is not awaiting payment"
        )

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    max_count = ((org.features if org else None) or {}).get("reminder_max_count", 3)
    sent_count = (
        db.query(ReceiptReminder)
        .filter(
            ReceiptReminder.receipt_id == receipt.id,
            ReceiptReminder.status == "sent",
        )
        .count()
    )
    if sent_count >= max_count:
        raise HTTPException(
            status_code=409, detail="Maximum number of reminders already sent"
        )

    try:
        reminder = send_reminder(db, receipt, "manual", user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(reminder)
    return reminder


@router.get("/{receipt_id}/reminders", response_model=list[ReceiptReminderResponse])
def list_receipt_reminders(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.read")),
):
    """List the reminders sent for a receipt, newest first."""
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return (
        db.query(ReceiptReminder)
        .filter(ReceiptReminder.receipt_id == receipt_id)
        .order_by(ReceiptReminder.sent_at.desc(), ReceiptReminder.id.desc())
        .all()
    )


@router.post("/{receipt_id}/cancel", response_model=ReceiptResponse)
def cancel_receipt_endpoint(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.write")),
):
    """Cancel a receipt."""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id, Receipt.is_active.is_(True)
    ).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    receipt = cancel_receipt(db, receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.post("/{receipt_id}/return", response_model=ReceiptResponse)
def return_receipt_endpoint(
    receipt_id: int,
    data: ReceiptReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.write")),
):
    """Mark a receipt as returned (rejected by bank)."""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id, Receipt.is_active.is_(True)
    ).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    receipt = return_receipt(db, receipt, data)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.post("/{receipt_id}/reemit", response_model=ReceiptResponse)
def reemit_receipt_endpoint(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.write")),
):
    """Re-emit a returned receipt — moves back to pending."""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id, Receipt.is_active.is_(True)
    ).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    receipt = reemit_receipt(db, receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


@member_router.get("/members/me/receipts")
def list_my_receipts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.billing.read")),
):
    """List current user's receipts (member self-service)."""
    member = _own_member(db, current_user)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    query = (
        db.query(Receipt)
        .filter(Receipt.member_id == member.id, Receipt.is_active.is_(True))
        .options(joinedload(Receipt.concept))
        .order_by(Receipt.emission_date.desc(), Receipt.id.desc())
    )

    items, meta = paginate(query, page, per_page)
    return {
        "items": [ReceiptResponse.model_validate(r) for r in items],
        "meta": meta.model_dump(),
    }


@router.post("/{receipt_id}/stripe/checkout")
def create_stripe_checkout(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.billing.write")),
):
    """Create a Stripe Checkout session for a receipt.

    Available to the receipt's owner (member) or any admin.
    Returns a redirect URL to the Stripe Checkout page.
    """
    from app.api.v1.endpoints.webhooks import get_adapter, _decrypt_provider_config
    from app.domains.billing.models import PaymentProvider
    from app.domains.billing.stripe_customer_service import ensure_customer
    from app.domains.organizations.models import OrganizationSettings

    receipt = (
        db.query(Receipt)
        .filter(Receipt.id == receipt_id, Receipt.is_active.is_(True))
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Auth: member can only pay own receipts
    _require_own_receipt(db, current_user, receipt, "billing.write")

    # Must be payable
    if receipt.status not in ("emitted", "overdue"):
        raise HTTPException(
            status_code=400,
            detail=f"Receipt status '{receipt.status}' is not payable",
        )

    # Find active Stripe provider
    provider = (
        db.query(PaymentProvider)
        .filter(
            PaymentProvider.provider_type == "stripe",
            PaymentProvider.status.in_(["active", "test"]),
        )
        .first()
    )
    if not provider:
        raise HTTPException(status_code=400, detail="No active Stripe provider configured")

    config = _decrypt_provider_config(provider)
    adapter = get_adapter("stripe", config)
    if not adapter:
        raise HTTPException(status_code=500, detail="Stripe adapter not available")

    # Get org currency
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    currency = org.currency if org and org.currency else "EUR"

    # Get member's person for customer sync
    member_obj = db.query(Member).filter(Member.id == receipt.member_id).first()
    person = db.query(Person).filter(Person.id == member_obj.person_id).first()

    # Lazy-create Stripe customer
    stripe_customer_id = None
    try:
        stripe_customer_id = ensure_customer(db, person, config["secret_key"])
    except Exception:
        pass  # Fall back to customer_email

    # Build return URLs
    from app.core.config import settings as app_settings
    base_url = app_settings.FRONTEND_URL.rstrip("/")
    success_url = f"{base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/payment/cancel?session_id={{CHECKOUT_SESSION_ID}}"

    result = adapter.create_payment(
        receipt=receipt,
        person=person,
        currency=currency,
        success_url=success_url,
        cancel_url=cancel_url,
        stripe_customer_id=stripe_customer_id,
    )

    # Store session ID on receipt
    receipt.stripe_checkout_session_id = result["session_id"]
    db.commit()

    return {
        "redirect_url": result["redirect_url"],
        "session_id": result["session_id"],
    }


@router.post("/{receipt_id}/redsys/initiate")
def initiate_redsys_payment(
    receipt_id: int,
    payload: dict | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.billing.write")),
):
    """Build signed Redsys form params for a browser redirect.

    The frontend receives `{redirect_url, form_params}` and auto-submits a
    hidden HTML form to the TPV. Authoritative payment status arrives on the
    async notification at `/webhooks/redsys`.

    Available to the receipt's owner (member) or any admin. Optional payload:
    `{"method": "card" | "bizum", "locale": "es" | "ca" | "en"}`.
    """
    from app.api.v1.endpoints.webhooks import _decrypt_provider_config, get_adapter
    from app.core.config import settings as app_settings
    from app.domains.billing.models import PaymentProvider

    method = (payload or {}).get("method", "card")
    locale = (payload or {}).get("locale", "es")
    if method not in ("card", "bizum"):
        raise HTTPException(status_code=400, detail="Invalid payment method")

    receipt = (
        db.query(Receipt)
        .filter(Receipt.id == receipt_id, Receipt.is_active.is_(True))
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    _require_own_receipt(db, current_user, receipt, "billing.write")

    if receipt.status not in ("emitted", "overdue"):
        raise HTTPException(
            status_code=400,
            detail=f"Receipt status '{receipt.status}' is not payable",
        )

    provider = (
        db.query(PaymentProvider)
        .filter(
            PaymentProvider.provider_type == "redsys",
            PaymentProvider.status.in_(["active", "test"]),
        )
        .first()
    )
    if not provider:
        raise HTTPException(status_code=400, detail="No active Redsys provider configured")

    config = _decrypt_provider_config(provider)
    adapter = get_adapter("redsys", config)
    if not adapter:
        raise HTTPException(status_code=500, detail="Redsys adapter not available")

    member_obj = db.query(Member).filter(Member.id == receipt.member_id).first()
    person = db.query(Person).filter(Person.id == member_obj.person_id).first()

    frontend = app_settings.FRONTEND_URL.rstrip("/")
    backend = app_settings.BACKEND_PUBLIC_URL.rstrip("/")
    success_url = f"{frontend}/payment/redsys/return?receipt_id={receipt.id}&outcome=ok"
    cancel_url = f"{frontend}/payment/redsys/return?receipt_id={receipt.id}&outcome=ko"
    merchant_url = f"{backend}/api/v1/webhooks/redsys"

    result = adapter.create_payment(
        receipt=receipt,
        person=person,
        success_url=success_url,
        cancel_url=cancel_url,
        merchant_url=merchant_url,
        method=method,
        locale=locale,
    )

    receipt.redsys_ds_order = result["ds_order"]
    if method == "bizum":
        receipt.payment_method = "bizum"
    db.commit()

    return {
        "redirect_url": result["redirect_url"],
        "form_params": result["form_params"],
        "ds_order": result["ds_order"],
    }


@router.get("/{receipt_id}/redsys/return")
def get_redsys_return_status(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.billing.read")),
):
    """Return the current receipt status for the Redsys return page to poll.

    Note: the browser redirect from Redsys is advisory — the authoritative
    status is set by the async notification handled at `/webhooks/redsys`.
    The return page polls this endpoint until `status` becomes `paid` or the
    polling window elapses.
    """
    receipt = (
        db.query(Receipt)
        .filter(Receipt.id == receipt_id, Receipt.is_active.is_(True))
        .options(joinedload(Receipt.member).joinedload(Member.person))
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    _require_own_receipt(db, current_user, receipt, "billing.read")

    return {
        "receipt_id": receipt.id,
        "receipt_number": receipt.receipt_number,
        "status": receipt.status,
        "payment_method": receipt.payment_method,
        "payment_date": receipt.payment_date.isoformat() if receipt.payment_date else None,
        "redsys_auth_code": receipt.redsys_auth_code,
        "ds_order": receipt.redsys_ds_order,
        "authoritative_note": (
            "Final status confirmed by async notification from Redsys."
        ),
    }


@router.get("/by-stripe-session/{session_id}")
def get_receipt_by_stripe_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.billing.read")),
):
    """Look up a receipt by Stripe Checkout session ID.

    Used by the payment success page to display receipt status
    without leaking receipt IDs in the URL.
    """
    receipt = (
        db.query(Receipt)
        .filter(
            Receipt.stripe_checkout_session_id == session_id,
            Receipt.is_active.is_(True),
        )
        .options(
            joinedload(Receipt.member).joinedload(Member.person),
            joinedload(Receipt.concept),
        )
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Auth: member can only see own receipts
    _require_own_receipt(db, current_user, receipt, "billing.read")

    return _to_detail(receipt)


@router.post("/generate-membership-fees")
def generate_membership_fees_endpoint(
    data: GenerateMembershipFeesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.run")),
):
    """Bulk generate membership fee receipts for all active members."""
    receipts = generate_membership_fees(db, data, current_user.id)
    db.commit()
    return {
        "generated": len(receipts),
        "receipt_ids": [r.id for r in receipts],
    }
