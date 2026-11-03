"""Which activity prices a member may hold, and what they are charged for one."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.authorization import user_has
from app.domains.activities.models import Activity, ActivityPrice
from app.domains.activities.schemas import ActivityPriceResponse
from app.domains.billing.service import activity_vat_rate, calculate_vat
from app.domains.members.models import Member


def priced(db: Session, activity: Activity, price: ActivityPrice) -> ActivityPriceResponse:
    """Attach what the member will actually be charged to a stored base price.

    Every response carrying a price goes through here: the schema defaults the
    VAT fields to 0, so a price serialized straight from the row reads as free.
    """
    rate = activity_vat_rate(db, activity.tax_rate)
    vat, total = calculate_vat(Decimal(str(price.amount)), rate)
    return ActivityPriceResponse.model_validate(price).model_copy(
        update={
            "vat_rate": float(rate),
            "vat_amount": float(vat),
            "total_amount": float(total),
        }
    )


def member_can_hold_price(price: ActivityPrice, member: Member) -> bool:
    """Whether this member may be charged this price.

    **The single definition of that question**, because it has to be answered in
    two places — what the member is offered, and what registration accepts — and
    two copies of it is exactly how the gap in #427 existed: a "member rate /
    general rate" pair enforced nothing, since registration only checked that
    the price belonged to the activity.

    Three conjuncts, and the middle one is a separate defect (#510):

    - ``is_active``: already enforced at registration.
    - ``is_visible``: was enforced **only in the browser**, so a member could
      register on a hidden price by posting its id. Folded in here rather than
      left for later, because leaving it out would mean writing a known bypass
      into a brand-new guard.
    - ``membership_type_ids``: empty or NULL means every type, so every price
      written before that column existed still applies to everyone.

    A member with no type matches only unrestricted prices. That is deliberate
    rather than incidental: a restriction naming specific types cannot be said
    to include a member who has none.
    """
    if not price.is_active or not price.is_visible:
        return False
    allowed = price.membership_type_ids
    if not allowed:
        return True
    return member.membership_type_id is not None and member.membership_type_id in allowed


def selectable_prices(activity: Activity, member: Member) -> list[ActivityPrice]:
    """The activity's prices this member may hold, in the stored display order."""
    return [p for p in activity.prices if member_can_hold_price(p, member)]


def prices_for_viewer(
    db: Session,
    activity: Activity,
    viewer,
    prices: list[ActivityPrice] | None = None,
) -> list[ActivityPrice]:
    """The prices this caller should be shown.

    Not the same question for an admin and for a member, and **two routes serve
    both**: ``GET /activities/{id}`` and ``GET /activities/{id}/prices`` each
    accept ``activities.read`` or ``self.activities.read``. So the narrowing is
    by permission rather than by endpoint — the shape
    ``get_visible_activity_or_404`` already uses for the activity itself — and
    it lives here so the two routes cannot drift apart.

    An admin managing prices must see every one, including those restricted to
    types they do not hold and those hidden from members.

    A caller without ``activities.read`` and without a member record keeps
    seeing everything, which is today's behaviour. Such an account is staff
    administering the club rather than a member of it, it cannot register at all
    (registration resolves a member row first), and narrowing it would be a new
    failure mode for a case nobody has characterised. The security property does
    not rest here regardless: ``member_can_hold_price`` is enforced in
    ``register_member``, where the price id actually arrives from the body.
    """
    candidates = activity.prices if prices is None else prices
    if viewer is None or user_has(viewer, "activities.read"):
        return list(candidates)
    member = (
        db.query(Member)
        .filter(Member.party_id == viewer.party_id)
        .order_by(Member.is_active.desc(), Member.id.desc())
        .first()
    )
    if member is None:
        return list(candidates)
    return [p for p in candidates if member_can_hold_price(p, member)]
