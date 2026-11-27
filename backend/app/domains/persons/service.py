"""Person service — writes that more than one domain has to get right.

Both functions here span the same seam, which is why they live below their
callers rather than in one of them. ``change_person_email`` keeps two rows in
different domains together: the address the organisation mails is a party fact
and the address someone signs in with is an auth fact. Putting it in ``members``
is what let a second endpoint write one without the other (#636).

``discard_unverified_account`` has the same shape. It is reached from the SSO
callback (#644) and from the scheduled sweep (#645), and what it deletes is a
party even though what prompts it is the state of an account.
"""

from sqlalchemy.orm import Session

from app.domains.auth.models import User
from app.domains.persons.models import Contact, ContactType, Party, Person


# The contact type meaning "the address the organisation writes to" (#473).
# ``email_work`` and ``email_other`` both read as secondary, so neither could
# carry it.
PRIMARY_EMAIL_TYPE_CODE = "email_main"


class EmailTaken(ValueError):
    """Another account already signs in with this address."""


class MissingPrimaryEmailType(RuntimeError):
    """The ``email_main`` contact type is absent, so no address can be stored.

    Seeded and installed by migration ``c8e4a7b2f193``. Raised rather than
    silently writing nothing, because a mailing address that vanishes without
    error is the failure this whole phase exists to avoid.
    """


def change_person_email(db: Session, person: Person, email: str | None) -> None:
    """Write a person's address to the party row and to their User row, if any.

    Login reads ``users.email`` while every mail the app sends reads the party's
    address through ``Person.email``, which is an association proxy onto
    ``Party.email``. Writing only the party row sends mail to the corrected
    address while sign-in still expects the old one, and nothing surfaces the
    split. The two rows are one address, so they move together.

    ``users.email`` is unique, so the address must not belong to another
    account. The party row is only checked against Users: a person with no login
    (an admin-created member) may share an address with one, as before, since a
    minor and a guardian legitimately do.

    This was #98, fixed in ``change_member_email`` and in the member update
    endpoint. ``PUT /persons/{id}`` assigned straight to the model and so had
    the same defect until #636; it is now the second caller of this function,
    which is why the function sits in ``persons`` rather than in ``members``.

    Since #473 the mailing address is written to the party's **primary email
    contact**, not to ``party.email``. The column is still what every reader
    reads, and a trigger keeps it equal to that contact, so writing the column
    here as well would be writing a cache by hand beside the thing that
    maintains it. One write path is the whole point: two is how #98 became #636.
    """
    user = person.user
    if user is not None:
        if not email:
            raise ValueError("A member with a login must keep an email address")
        taken = (
            db.query(User).filter(User.email == email, User.id != user.id).first()
        )
        if taken:
            raise EmailTaken("Email already registered")
        user.email = email
    set_primary_email_contact(db, person.party_id, email)


def set_primary_email_contact(db: Session, party_id: int, email: str | None) -> None:
    """Put ``email`` on the party's primary email contact, creating it if needed.

    The source of truth for the address the organisation writes to (#473).
    ``party.email`` follows it by trigger, so nothing here touches that column.

    A blank address removes the contact rather than storing an empty string: the
    trigger reads "no primary email contact" as "no address", and an empty row
    would make ``party.email`` the empty string instead of NULL, which every
    ``if person.email`` reader in the mail paths would then treat as a usable
    address.
    """
    contact_type = (
        db.query(ContactType).filter(ContactType.code == PRIMARY_EMAIL_TYPE_CODE).first()
    )
    if contact_type is None:
        raise MissingPrimaryEmailType(PRIMARY_EMAIL_TYPE_CODE)

    existing = (
        db.query(Contact)
        .filter(
            Contact.party_id == party_id,
            Contact.channel == "email",
            Contact.is_primary.is_(True),
        )
        .first()
    )

    if not email:
        if existing is not None:
            db.delete(existing)
            db.flush()
            _refresh_cached_party_email(db, party_id)
        return

    if existing is None:
        db.add(
            Contact(
                party_id=party_id,
                contact_type_id=contact_type.id,
                value=email,
                is_primary=True,
            )
        )
    else:
        existing.value = email
    db.flush()
    _refresh_cached_party_email(db, party_id)


def _refresh_cached_party_email(db: Session, party_id: int) -> None:
    """Let the session see what the trigger just wrote.

    The trigger updates ``party.email`` behind SQLAlchemy's back, so an
    identity-mapped ``Party`` loaded earlier in the request still holds the old
    address and ``person.email`` reads it through the association proxy. Code
    that writes the address and then reads it back — the member update endpoint
    building its response is exactly that — would otherwise see the value it
    replaced.

    Expiring the attribute rather than assigning it keeps the database the only
    writer of this column. Assigning would have Python and the trigger both
    computing it, which is two sources of truth for a cache that exists to have
    one. ``trg_party_display_name`` solved the same problem the other way round,
    but there the value did not exist in the database yet.
    """
    party = db.get(Party, party_id)
    if party is not None:
        db.expire(party, ["email"])


class UnverifiedAccountHasHistory(Exception):
    """An unverified account holds financial history, so it cannot be discarded.

    Unreachable once approval requires a verified address (#643): a registration
    nobody confirmed can no longer be approved, so it can hold neither a member
    number nor a receipt. Kept because the alternative failure is worse than the
    exception. ``receipts.party_id`` and ``sepa_mandates.party_id`` carry no
    ``ondelete``, so the database would refuse the delete and the caller would
    see an ``IntegrityError`` out of an authentication callback, which reads as
    a broken sign-in rather than as a refusal.
    """


def discard_unverified_account(db: Session, user: User) -> None:
    """Delete the party behind an unverified account, so its address is free.

    The **party**, not the ``users`` row. The abandoned registration created a
    Person, a Party and a pending Member, and deleting only the login would
    orphan all three, leave the address sitting on the party row, and hand the
    replacement account a second set of each. Everything else the party owns —
    contacts, addresses, bank accounts, the member record — cascades with it.

    Called from the SSO callback when a provider-verified sign-in claims the
    address (#644), and from the scheduled sweep for the accounts nobody ever
    comes back for (#645). One implementation, because two copies of a rule
    about these rows is exactly how #98 became #636.

    The audit entry is written before the delete and deliberately carries no
    ``user_id``: there is no acting user in a provider callback, and the column
    is ``ON DELETE SET NULL`` against the row being removed, so recording the
    discarded account there would blank itself out. The detail goes in
    ``old_values``, which nothing cascades into.
    """
    from app.domains.audit.models import AuditLog
    from app.domains.billing.models import Receipt, SepaMandate

    party_id = user.party_id
    blocked = (
        db.query(Receipt).filter(Receipt.party_id == party_id).count()
        + db.query(SepaMandate).filter(SepaMandate.party_id == party_id).count()
    )
    if blocked:
        raise UnverifiedAccountHasHistory(user.email)

    db.add(
        AuditLog(
            table_name="party",
            record_id=party_id,
            action="delete",
            user_id=None,
            old_values={
                "email": user.email,
                "user_id": user.id,
                "reason": "unverified account replaced by a provider-verified sign-in",
            },
        )
    )
    db.flush()

    party = db.query(Party).filter(Party.id == party_id).first()
    if party is not None:
        db.delete(party)
    db.flush()
