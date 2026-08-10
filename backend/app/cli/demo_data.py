"""Demo dataset generators — a realistic Spanish sports/cultural-club year.

Layered on top of the base install by ``python -m app.cli.seed --demo``. Where
the ``--test`` seeders produce a small fixed fixture, this module produces a
*year-spread* dataset so the admin dashboard finance graph and the annual
summary have real monthly revenue, outstanding, and membership-growth curves.

Everything is idempotent: each generator early-returns if its data is already
present, so re-running ``--demo`` adds nothing.

Demo records are namespaced (member emails ``demo{n}@mediterrani.example``,
receipt numbers ``DEMO-{year}-{seq}``) so they never collide with ``--test``
fixtures. Randomness is seeded for reproducible screenshots.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from app.domains.billing.models import Concept, PaymentProvider, Receipt, SepaMandate
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person
from app.domains.reminders.models import Reminder

# Deterministic so the same demo dataset (and screenshots) reproduce every run.
_rng = random.Random(20260707)

FIRST_NAMES = [
    "María", "Joan", "Laura", "Carlos", "Anna", "Marta", "Jordi", "Elena",
    "Àlex", "Núria", "Marc", "Carla", "Pau", "Laia", "Oriol", "Gemma",
    "Arnau", "Sílvia", "David", "Montse", "Ferran", "Aina", "Pol", "Júlia",
    "Sergi", "Clara", "Guillem", "Berta", "Roger", "Ona", "Biel", "Emma",
    "Nil", "Judit", "Èric", "Mar", "Bruno", "Irene", "Adrià", "Paula",
]

LAST_NAMES = [
    "García", "Puig", "Martínez", "López", "Ferrer", "Soler", "Vidal", "Ruiz",
    "Serra", "Blanch", "Roca", "Pons", "Mas", "Font", "Casals", "Rovira",
    "Bosch", "Esteve", "Navarro", "Costa", "Aguilar", "Torrent", "Sala",
    "Fuster", "Ribas", "Molina", "Carbó", "Prat", "Vila", "Camps",
]

# Status mix: active-heavy, with every status represented so the dashboard
# member counters and the annual summary's lost-members figure light up.
STATUS_WEIGHTS = (
    ["active"] * 44
    + ["pending"] * 6
    + ["suspended"] * 3
    + ["expired"] * 4
    + ["cancelled"] * 3
)

IBANS = [
    ("ES6621000418401234567891", "CAIXESBBXXX"),
    ("ES7920385778983000760236", "CAIXESBBXXX"),
    ("ES9121000418450200051332", "CAIXESBBXXX"),
    ("ES8023100001180000012345", "CAIXESBBXXX"),
    ("ES6000491500051234567892", "BSCHESMMXXX"),
    ("ES2100820532161234567890", "BSABESBBXXX"),
    ("ES7100302053091234567895", "BARKESMMXXX"),
    ("ES3801822200160201234567", "BBVAESMMXXX"),
]

GENDERS = ["female", "male", "male", "female", "non_binary"]


def generate_members(
    db, default_membership_type: MembershipType, n: int = 60
) -> list[Member]:
    """Create ~n demo members with Spanish names, all statuses, and joined_at
    spread across the current year (plus a few from the prior year).

    Idempotent: skips entirely if the demo cohort already exists. Demo members
    carry their own ``D-`` member-number namespace so they never collide with
    base-install / ``--test`` numbering.
    """
    if db.query(Person).filter(Person.email.like("demo%@mediterrani.example")).first():
        print("  Demo members: already seeded")
        return demo_members(db)

    types = db.query(MembershipType).filter(MembershipType.is_active.is_(True)).all()
    type_ids = [mt.id for mt in types] or [default_membership_type.id]

    today = date.today()
    year = today.year

    # Weighted status list, sized to n and shuffled so the mix interleaves
    # (rather than front-loading every active member) while keeping proportions.
    statuses = (STATUS_WEIGHTS * (n // len(STATUS_WEIGHTS) + 1))[:n]
    _rng.shuffle(statuses)

    members: list[Member] = []
    for i in range(n):
        first = _rng.choice(FIRST_NAMES)
        last = f"{_rng.choice(LAST_NAMES)} {_rng.choice(LAST_NAMES)}"
        status = statuses[i]

        # Spread join dates: most joined earlier in the year (up to today), a
        # handful carried over from last year so year-end totals are realistic.
        if i % 9 == 0:
            joined = date(year - 1, _rng.randint(1, 12), _rng.randint(1, 28))
        else:
            month = _rng.randint(1, max(1, today.month))
            day = _rng.randint(1, 28)
            joined = min(date(year, month, day), today)

        person = Person(
            first_name=first,
            last_name=last,
            email=f"demo{i}@mediterrani.example",
            gender=_rng.choice(GENDERS),
            date_of_birth=date(_rng.randint(1965, 2010), _rng.randint(1, 12), _rng.randint(1, 28)),
        )
        # ~40% pay by direct debit — gives SEPA + paid receipts something to bind to.
        if _rng.random() < 0.4:
            iban, bic = _rng.choice(IBANS)
            person.bank_iban = iban
            person.bank_bic = bic
            person.bank_holder_name = f"{first} {last}"
            person.payment_method = "direct_debit"
        db.add(person)
        db.flush()

        member = Member(
            person_id=person.id,
            membership_type_id=type_ids[i % len(type_ids)],
            member_number=f"D-{i + 1:04d}",
            status=status,
            joined_at=joined,
        )
        # Members lost this year: stamp status_changed_at within the year so the
        # annual summary counts them as lost (and nets them out of growth).
        if status in ("cancelled", "expired"):
            member.status_changed_at = datetime(
                year, _rng.randint(1, max(1, today.month)), _rng.randint(1, 28),
                tzinfo=timezone.utc,
            )
        db.add(member)
        db.flush()
        members.append(member)

    print(f"  Demo members: created {len(members)} (all statuses, joined_at across {year})")
    return members


def demo_members(db) -> list[Member]:
    return (
        db.query(Member)
        .join(Person, Member.person_id == Person.id)
        .filter(Person.email.like("demo%@mediterrani.example"))
        .all()
    )


def _concepts(db) -> dict[str, Concept]:
    """Reuse existing membership concepts, or create a minimal set for demo."""
    existing = {c.code: c for c in db.query(Concept).all()}
    if existing:
        return existing

    concepts = {
        "membership-full-member": Concept(
            name="Quota Soci — Anual", code="membership-full-member",
            concept_type="membership", default_amount=600.00, vat_rate=21.00,
        ),
        "membership-student": Concept(
            name="Quota Estudiant — Anual", code="membership-student",
            concept_type="membership", default_amount=300.00, vat_rate=21.00,
        ),
        "manual-other": Concept(
            name="Altres Conceptes", code="manual-other",
            concept_type="manual", default_amount=0, vat_rate=21.00,
        ),
    }
    for c in concepts.values():
        db.add(c)
    db.flush()
    return concepts


def generate_billing(db, created_by: int | None) -> None:
    """Create membership receipts spread across every month of the year so the
    finance graph and annual summary have real monthly revenue + outstanding.

    Statuses cover every state; paid receipts carry a payment_date within their
    month (revenue), unpaid ones an emission_date within their month
    (outstanding). Idempotent via the ``DEMO-`` receipt-number namespace.
    """
    if db.query(Receipt).filter(Receipt.receipt_number.like("DEMO-%")).first():
        print("  Demo billing: already seeded")
        return

    concepts = _concepts(db)
    membership_concept = (
        concepts.get("membership-full-member") or next(iter(concepts.values()))
    )

    members = demo_members(db)
    if not members:
        print("  Demo billing: no demo members to bill")
        return

    today = date.today()
    year = today.year
    seq = 0
    counts: dict[str, int] = {}

    # Weighted status pool per receipt — paid-heavy so revenue dominates, but
    # every state appears for the receipts list + counters.
    status_pool = (
        ["paid"] * 6 + ["emitted"] * 3 + ["pending"] * 2
        + ["overdue", "returned", "cancelled", "new"]
    )

    for month in range(1, today.month + 1):
        # A slice of members billed each month → revenue in every month.
        monthly = _rng.sample(members, min(len(members), _rng.randint(6, 10)))
        for member in monthly:
            status = _rng.choice(status_pool)
            emission = date(year, month, _rng.randint(1, 28))
            base = Decimal(str(membership_concept.default_amount or 300)) / Decimal("12")
            base = base.quantize(Decimal("0.01"))
            vat_rate = Decimal(str(membership_concept.vat_rate or 21))
            vat = (base * vat_rate / Decimal("100")).quantize(Decimal("0.01"))
            total = base + vat

            pay_method = None
            pay_date = None
            if status == "paid":
                pay_method = "direct_debit"
                pay_date = emission + timedelta(days=_rng.randint(1, 20))
                if pay_date > today:
                    pay_date = today

            seq += 1
            receipt = Receipt(
                receipt_number=f"DEMO-{year}-{seq:04d}",
                member_id=member.id,
                concept_id=membership_concept.id,
                origin="membership",
                description=f"Quota mensual {month:02d}/{year}",
                base_amount=base,
                vat_rate=vat_rate,
                vat_amount=vat,
                total_amount=total,
                status=status,
                payment_method=pay_method,
                emission_date=emission,
                due_date=emission + timedelta(days=30),
                payment_date=pay_date,
                return_date=(emission + timedelta(days=20)) if status == "returned" else None,
                return_reason="Fondos insuficientes" if status == "returned" else None,
                billing_period_start=date(year, month, 1),
                billing_period_end=date(year, month, 28),
                is_batchable=True,
                created_by=created_by,
            )
            db.add(receipt)
            counts[status] = counts.get(status, 0) + 1

    db.flush()
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    print(f"  Demo billing: created {seq} receipts across {today.month} months ({summary})")


def generate_sepa(db) -> None:
    """Ensure a SEPA provider exists and create mandates for demo members with
    IBANs (mostly active, a couple cancelled). Idempotent."""
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if org and not org.creditor_id:
        org.creditor_id = "ES12000B12345678"
        org.sepa_format = "pain.008"
        db.flush()

    if not db.query(PaymentProvider).filter(PaymentProvider.provider_type == "sepa_direct_debit").first():
        db.add(PaymentProvider(
            provider_type="sepa_direct_debit",
            display_name="SEPA Direct Debit",
            status="active",
            config={"format": "pain.008.001.02"},
            is_default=True,
        ))
        db.flush()

    # Demo members with an IBAN but no mandate yet.
    candidates = (
        db.query(Member, Person)
        .join(Person, Member.person_id == Person.id)
        .filter(
            Person.email.like("demo%@mediterrani.example"),
            Person.bank_iban.isnot(None),
        )
        .all()
    )
    today = date.today()
    created = 0
    for idx, (member, person) in enumerate(candidates):
        if db.query(SepaMandate).filter(SepaMandate.member_id == member.id).first():
            continue
        status = "cancelled" if idx % 8 == 7 else "active"
        signed = today - timedelta(days=60 + idx * 3)
        db.add(SepaMandate(
            member_id=member.id,
            mandate_reference=f"DEMO-{member.member_number}-{idx + 1:03d}",
            creditor_id=org.creditor_id if org else "ES12000B12345678",
            debtor_name=f"{person.first_name} {person.last_name}",
            debtor_iban=person.bank_iban,
            debtor_bic=person.bank_bic,
            mandate_type="recurrent",
            signature_method="paper",
            status=status,
            signed_at=signed,
            cancelled_at=today - timedelta(days=5) if status == "cancelled" else None,
        ))
        created += 1

    db.flush()
    if created:
        print(f"  Demo SEPA: created {created} mandates")
    else:
        print("  Demo SEPA: already seeded")


def generate_reminders(db, created_by: int | None) -> None:
    """Seed a handful of admin notes + dated reminders (open/overdue/this-week)
    so the dashboard rail widget is populated. Idempotent."""
    if db.query(Reminder).first():
        print("  Demo reminders: already present")
        return

    today = date.today()
    items = [
        ("Preparar la remesa SEPA del mes", today + timedelta(days=3)),
        ("Renovar el conveni amb l'ajuntament", today + timedelta(days=6)),
        ("Trucar al proveïdor de material esportiu", today - timedelta(days=2)),
        ("Revisar les altes de socis pendents", today),
        ("Actualitzar el quadre de quotes per a la nova temporada", None),
        ("Enviar el recordatori de l'assemblea general", None),
    ]
    for content, due in items:
        db.add(Reminder(content=content, due_date=due, created_by=created_by))
    db.flush()
    print(f"  Demo reminders: created {len(items)} (notes + dated)")


def _next_date_for(weekday: int, min_ahead: int = 1) -> date:
    """The next occurrence of ``weekday`` (0=Mon) at least ``min_ahead`` days ahead."""
    today = date.today()
    delta = (weekday - today.weekday()) % 7
    if delta < min_ahead:
        delta += 7
    return today + timedelta(days=delta)


def generate_bookings(db) -> None:
    """Enable Simple Bookings and seed spaces, dated slots and demo bookings.

    Two spaces: a capacity-1 padel court (singles, with a waitlist demo) and a
    capacity-6 group-class room. Slots land on the next upcoming occurrence of
    their weekday, within the booking window; the group class is generated as a
    series (shared series_id) like the admin repeat rule would.
    """
    from app.domains.bookings.models import Booking, Space, SpaceSlot

    if db.query(Space).first() is not None:
        return  # already seeded

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if org is not None:
        features = dict(org.features or {})
        features.update(
            {
                "bookings": True,
                "booking_window_days": 14,
                "booking_cancellation_deadline_hours": 24,
                "booking_waitlist_enabled": True,
            }
        )
        org.features = features

    members = demo_members(db)
    if not members:
        return

    padel = Space(
        name="Pista de pádel 1",
        space_type="court",
        description="Pista individual, reserva por franjas",
        open_time=time(8, 0),
        close_time=time(22, 0),
        is_active=True,
    )
    sala = Space(
        name="Sala polivalente",
        space_type="room",
        description="Clases dirigidas en grupo",
        open_time=time(9, 0),
        close_time=time(21, 0),
        is_active=True,
    )
    db.add_all([padel, sala])
    db.flush()

    # Padel: capacity-1 singles slots on the next Mon/Wed mornings + Fri evening.
    padel_slots: list[SpaceSlot] = []
    for weekday, start, end in [
        (0, time(10, 0), time(11, 0)),
        (2, time(10, 0), time(11, 0)),
        (4, time(18, 0), time(19, 0)),
    ]:
        slot = SpaceSlot(
            space_id=padel.id, slot_date=_next_date_for(weekday),
            start_time=start, end_time=end, capacity=1, is_active=True,
        )
        db.add(slot)
        padel_slots.append(slot)

    # Sala: capacity-6 group class on the next Tue/Thu evenings, generated as
    # one series (shared series_id) like the admin repeat rule would.
    from uuid import uuid4

    sala_series = uuid4()
    sala_slots: list[SpaceSlot] = []
    for weekday in (1, 3):
        slot = SpaceSlot(
            space_id=sala.id, slot_date=_next_date_for(weekday),
            start_time=time(19, 0), end_time=time(20, 0),
            capacity=6, series_id=sala_series, is_active=True,
        )
        db.add(slot)
        sala_slots.append(slot)
    db.flush()

    pool = list(members)
    cursor = 0

    def take() -> Member:
        nonlocal cursor
        member = pool[cursor % len(pool)]
        cursor += 1
        return member

    # Padel (capacity 1): one confirmed booking each; the first slot also gets a
    # waitlisted member so the waitlist/promotion flow is visible in the demo.
    for i, slot in enumerate(padel_slots):
        db.add(Booking(space_slot_id=slot.id, member_id=take().id,
                       status="booked"))
        if i == 0:
            db.add(Booking(space_slot_id=slot.id, member_id=take().id,
                           status="waitlisted",
                           waitlisted_at=datetime.now(timezone.utc)))

    # Sala (capacity 6): four confirmed bookings on each class.
    for slot in sala_slots:
        for _ in range(4):
            db.add(Booking(space_slot_id=slot.id, member_id=take().id,
                           status="booked"))

    db.flush()
    print(
        f"  Bookings: 2 spaces, {len(padel_slots) + len(sala_slots)} slots, "
        "demo bookings + a waitlist"
    )


def seed_demo_data(db, default_membership_type: MembershipType, created_by: int | None) -> None:
    """Orchestrate the demo dataset on top of the base install.

    Reuses the ``--test`` activity + registration seeders (they operate on
    whatever active members / published activities exist) and layers the
    year-spread members, billing, SEPA, and reminders on top.
    """
    from app.cli.seed import seed_activities, seed_registrations

    print("\nSeeding demo members...")
    generate_members(db, default_membership_type)

    print("\nSeeding demo activities...")
    if created_by is not None:
        seed_activities(db, created_by)

    print("\nSeeding demo registrations...")
    seed_registrations(db)

    print("\nSeeding demo billing...")
    generate_billing(db, created_by)

    print("\nSeeding demo SEPA...")
    generate_sepa(db)

    print("\nSeeding demo reminders...")
    generate_reminders(db, created_by)

    print("\nSeeding demo bookings...")
    generate_bookings(db)
