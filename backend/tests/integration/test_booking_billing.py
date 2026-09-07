"""Every path that confirms a booking must invoice it, and no admin action may
destroy the invoice.

Two failures are covered here that nothing else would catch. The first is the
waitlist: a member promoted into a paid slot holds exactly what a member who
booked it directly holds, and billing only the direct path leaks money silently,
because nothing reconciles bookings against receipts. The second is deletion —
``bookings.space_slot_id`` cascades and ``delete_slot(force=True)`` deletes the
slot row, so a receipt pointing at a booking has to survive its subject.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.domains.billing.models import Concept, Receipt
from app.domains.billing.service import mark_receipt_paid
from app.domains.bookings import service
from app.domains.bookings.billing import ensure_booking_receipt
from app.domains.bookings.models import Booking, Space, SpaceSlot
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

PRICE = Decimal("10.00")
#: 10.00 plus the org's default 21% VAT.
TOTAL = Decimal("12.10")


def _org(db, **features):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1,
            name="Club",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
        )
        db.add(org)
    org.default_vat_rate = 21
    org.features = {"bookings": True, **features}
    db.flush()
    return org


def _member(db, i=0):
    person = Person(first_name=f"B{i}", last_name="Payer", email=f"b{i}@bill.com")
    db.add(person)
    db.flush()
    member = Member(person_id=person.id, status="active", is_active=True)
    db.add(member)
    db.flush()
    return member


def _space(db, price=None):
    space = Space(
        name="Court 1",
        open_time=time(8, 0),
        close_time=time(22, 0),
        is_active=True,
        price=price,
    )
    db.add(space)
    db.flush()
    return space


def _slot(db, space, on=None, capacity=1, price=None):
    slot = SpaceSlot(
        space_id=space.id,
        slot_date=on or (date.today() + timedelta(days=3)),
        start_time=time(10, 0),
        end_time=time(11, 0),
        capacity=capacity,
        price=price,
        is_active=True,
    )
    db.add(slot)
    db.flush()
    return slot


def _user(db):
    from app.core.security.password import hash_password
    from app.domains.auth.models import User

    person = Person(first_name="U", last_name="ser", email="canceller@bill.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email="canceller@bill.com",
        password_hash=hash_password("x"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _receipts(db, booking_id):
    return (
        db.query(Receipt)
        .filter(Receipt.booking_id == booking_id)
        .order_by(Receipt.id)
        .all()
    )


# --- A price on the space is what gets billed ------------------------------


def test_free_space_raises_no_receipt(db):
    _org(db)
    space = _space(db)
    slot = _slot(db, space)

    booking = service.create_booking(db, _member(db, 1), slot.id)

    assert _receipts(db, booking.id) == []


def test_paid_space_bills_the_confirmed_booking(db):
    _org(db)
    space = _space(db, price=PRICE)
    slot = _slot(db, space)
    member = _member(db, 1)

    booking = service.create_booking(db, member, slot.id)

    receipt = _receipts(db, booking.id)[0]
    assert receipt.origin == "booking"
    assert receipt.member_id == member.id
    assert receipt.status == "emitted"
    assert receipt.base_amount == PRICE
    assert receipt.total_amount == TOTAL
    # The description has to stand on its own — the link back is breakable.
    assert space.name in receipt.description
    assert slot.slot_date.strftime("%d/%m/%Y") in receipt.description


def test_booking_concept_is_found_or_created_once(db):
    _org(db)
    space = _space(db, price=PRICE)
    member = _member(db, 1)
    for day in (3, 4):
        slot = _slot(db, space, on=date.today() + timedelta(days=day))
        service.create_booking(db, member, slot.id)

    concepts = db.query(Concept).filter(Concept.code == "space-booking").all()
    assert len(concepts) == 1
    assert concepts[0].concept_type == "booking"


def test_slot_price_overrides_the_space_price(db):
    _org(db)
    space = _space(db, price=PRICE)
    slot = _slot(db, space, price=Decimal("25.00"))

    booking = service.create_booking(db, _member(db, 1), slot.id)

    assert _receipts(db, booking.id)[0].base_amount == Decimal("25.00")


def test_slot_priced_at_zero_is_free_in_a_paid_space(db):
    _org(db)
    space = _space(db, price=PRICE)
    slot = _slot(db, space, price=Decimal("0"))

    booking = service.create_booking(db, _member(db, 1), slot.id)

    assert _receipts(db, booking.id) == []


def test_waitlisted_booking_is_not_billed_until_it_is_confirmed(db):
    _org(db)
    space = _space(db, price=PRICE)
    slot = _slot(db, space, capacity=1)
    service.create_booking(db, _member(db, 1), slot.id)

    waiting = service.create_booking(db, _member(db, 2), slot.id)

    assert waiting.status == "waitlisted"
    assert _receipts(db, waiting.id) == []


# --- Promotion is a confirmation path, so it bills too ---------------------


def test_waitlist_promotion_bills_the_promoted_member(db):
    _org(db)
    space = _space(db, price=PRICE)
    slot = _slot(db, space, capacity=1)
    holder = service.create_booking(db, _member(db, 1), slot.id)
    promoted = service.create_booking(db, _member(db, 2), slot.id)
    user = _user(db)

    service.cancel_booking(db, holder, cancelled_by_user_id=user.id, is_admin=True)

    assert promoted.status == "booked"
    receipt = _receipts(db, promoted.id)[0]
    assert receipt.status == "emitted"
    assert receipt.total_amount == TOTAL


def test_billing_a_booking_twice_raises_one_receipt(db):
    _org(db)
    space = _space(db, price=PRICE)
    slot = _slot(db, space)
    booking = service.create_booking(db, _member(db, 1), slot.id)

    ensure_booking_receipt(db, booking, slot, space)
    ensure_booking_receipt(db, booking, slot, space)

    assert len(_receipts(db, booking.id)) == 1


# --- Cancellation: void what is unpaid, leave what is paid -----------------


def test_cancelling_voids_the_unpaid_receipt(db):
    _org(db)
    space = _space(db, price=PRICE)
    slot = _slot(db, space)
    booking = service.create_booking(db, _member(db, 1), slot.id)
    user = _user(db)

    service.cancel_booking(db, booking, cancelled_by_user_id=user.id, is_admin=True)

    assert _receipts(db, booking.id)[0].status == "cancelled"


def test_cancelling_leaves_a_paid_receipt_standing(db):
    """There is no refund path — no credit notes, no refund API. A paid receipt
    records money that changed hands, and the club settles it offline."""
    _org(db)
    space = _space(db, price=PRICE)
    slot = _slot(db, space)
    booking = service.create_booking(db, _member(db, 1), slot.id)
    mark_receipt_paid(db, _receipts(db, booking.id)[0], payment_method="cash")
    user = _user(db)

    service.cancel_booking(db, booking, cancelled_by_user_id=user.id, is_admin=True)

    assert _receipts(db, booking.id)[0].status == "paid"


def test_rebooking_after_a_cancellation_owes_again(db):
    _org(db)
    space = _space(db, price=PRICE)
    slot = _slot(db, space)
    member = _member(db, 1)
    first = service.create_booking(db, member, slot.id)
    user = _user(db)
    service.cancel_booking(db, first, cancelled_by_user_id=user.id, is_admin=True)

    second = service.create_booking(db, member, slot.id)

    assert _receipts(db, first.id)[0].status == "cancelled"
    assert _receipts(db, second.id)[0].status == "emitted"


# --- Deleting a slot must not delete the money ----------------------------


def test_receipt_booking_fk_is_set_null_on_delete(db):
    """The shape the deletion test depends on, asserted directly.

    ``registration_id`` carries no ``ondelete`` and gets away with it only
    because registrations are never hard-deleted. Copying that shape here would
    make ``delete_slot(force=True)`` fail with a foreign key violation as soon as
    an affected booking had a receipt — and the ORM's own nullification would
    hide the mistake from the test below, which is why the catalog is read.
    """
    rule = db.execute(
        text(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE contype = 'f' "
            "AND conrelid = 'receipts'::regclass "
            "AND confrelid = 'bookings'::regclass"
        )
    ).scalar_one()
    # 'n' = SET NULL, 'a' = NO ACTION, 'c' = CASCADE.
    assert rule == "n"


def test_forced_slot_delete_succeeds_and_the_receipt_survives(db):
    _org(db)
    space = _space(db, price=PRICE)
    slot = _slot(db, space)
    booking = service.create_booking(db, _member(db, 1), slot.id)
    receipt_id = _receipts(db, booking.id)[0].id

    service.delete_slot(db, slot, force=True)
    db.flush()
    db.expire_all()

    assert db.query(Booking).filter(Booking.id == booking.id).first() is None
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).one()
    assert receipt.booking_id is None
    assert receipt.status == "emitted"
    assert receipt.total_amount == TOTAL
    # The invoice line still says what was sold, with nothing left to join to.
    assert "Court 1" in receipt.description


def test_forced_space_delete_succeeds_and_the_receipt_survives(db):
    _org(db)
    space = _space(db, price=PRICE)
    slot = _slot(db, space)
    booking = service.create_booking(db, _member(db, 1), slot.id)
    receipt_id = _receipts(db, booking.id)[0].id

    service.delete_space(db, space, force=True)
    db.flush()
    db.expire_all()

    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).one()
    assert receipt.booking_id is None
    assert receipt.status == "emitted"
