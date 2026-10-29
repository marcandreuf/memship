"""Party, Person, Address, and Contact models."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    insert,
)
from sqlalchemy import DDL
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import relationship, validates

from app.core.schema_types import normalize_email
from app.db.base import Base




class PartyKind(Base):
    """Registry of party kinds — adding one is an INSERT, not a constraint rewrite."""

    __tablename__ = "party_kinds"

    code = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    # Is there a natural person behind this kind? Decides whether a date of
    # birth, a guardian or an age band mean anything.
    is_natural = Column(Boolean, nullable=False, server_default="false")
    display_order = Column(Integer, nullable=False, server_default="0")


class Party(Base):
    """The identity root: anyone the organisation holds a record of (ADR 0003).

    Plumbing, not a product concept — it has no screen of its own. ``persons``
    is its first subtype; a company is a party with ``kind='company'`` and no
    subtype row at all, which is what lets a donation be recorded without
    inventing a member. ``UNIQUE (id, kind)`` is the target of the subtypes'
    composite foreign keys: together with each subtype's pinned ``kind`` it
    makes subtypes mutually exclusive in the database.
    """

    __tablename__ = "party"
    __table_args__ = (
        UniqueConstraint("id", "kind", name="party_id_kind_key"),
        Index("ix_party_kind", "kind"),
        Index("ix_party_display_name", "display_name"),
        Index("ix_party_national_id", "national_id", postgresql_where="national_id IS NOT NULL"),
        Index("ix_party_email", "email", postgresql_where="email IS NOT NULL"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    kind = Column(Text, ForeignKey("party_kinds.code", name="party_kind_fkey"), nullable=False)
    # Maintained from the subtype. The one denormalisation worth taking: every
    # list, receipt PDF and SEPA file wants a name and should not care what
    # kind of party it is. ``sepa_mandates.debtor_name`` set the precedent.
    display_name = Column(Text, nullable=False)
    # Party-level facts: a company has all of these too. Since the Phase 3
    # column drop these are the only copy; ``Person`` reaches them through
    # association proxies.
    national_id = Column(String(50))
    email = Column(String(255))
    photo_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @validates("email")
    def _normalise_email(self, _key, value):
        """Same rule as ``User.email`` — see the validator there (#191).

        Lived on ``Person`` while the column did; the fact moved up, the rule
        moves with it. Deliberately not unique (a minor shares a guardian's
        address). ``attach_login`` copies it into ``users.email``, where it
        decides a login.
        """
        return normalize_email(value)


class Person(Base):
    __tablename__ = "persons"
    __table_args__ = (
        # The composite FK plus the pinned ``kind`` is what makes subtypes
        # mutually exclusive: a persons row can only attach to a party whose
        # kind is 'person', so no party can ever hold two different subtypes.
        ForeignKeyConstraint(
            ["party_id", "kind"],
            ["party.id", "party.kind"],
            name="persons_party_fk",
            ondelete="CASCADE",
        ),
        CheckConstraint("kind = 'person'", name="persons_kind_check"),
        Index("idx_persons_last_name", "last_name"),
    )

    # The party IS the identity: persons dropped its own serial in Phase 3 and
    # the subtype keys on its party. The value is assigned by the
    # ``before_insert`` event below (or by the pending Party flushing first),
    # never by a persons-side sequence.
    party_id = Column(BigInteger, primary_key=True, autoincrement=False)
    # Holds no information (always 'person') — it exists so the foreign key
    # above can be composite. See Party.
    kind = Column(Text, nullable=False, server_default="person")
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date)
    gender = Column(String(20))
    bank_iban = Column(String(34))
    bank_bic = Column(String(11))
    bank_holder_name = Column(String(255))
    payment_method = Column(String(20))
    stripe_customer_id = Column(String(255), unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships. ``party`` eager-joins because the proxies below make it
    # part of what a person IS — email, national id and photo live there, and
    # a lazy load per row would turn every loop over persons into N+1.
    party = relationship(
        "Party",
        foreign_keys=[party_id],
        primaryjoin="Person.party_id == Party.id",
        lazy="joined",
        innerjoin=True,
    )
    user = relationship(
        "User",
        primaryjoin="Person.party_id == foreign(User.party_id)",
        uselist=False,
        viewonly=True,
    )
    member = relationship(
        "Member",
        primaryjoin="Person.party_id == foreign(Member.party_id)",
        uselist=False,
        viewonly=True,
    )
    addresses = relationship(
        "Address",
        back_populates="person",
        primaryjoin="Person.party_id == foreign(Address.party_id)",
        viewonly=True,
    )
    contacts = relationship(
        "Contact",
        back_populates="person",
        primaryjoin="Person.party_id == foreign(Contact.party_id)",
        viewonly=True,
    )

    # The party-level facts, readable and writable as if they were still
    # columns here. Setting one on a brand-new person creates the pending
    # Party (the creator), which then flushes before the person and supplies
    # its ``party_id``. Class-level use supports equality (an EXISTS against
    # party); anything richer — LIKE, a select column — must join ``Party``
    # explicitly, and fails loudly here rather than silently matching nothing.
    email = association_proxy(
        "party", "email",
        creator=lambda value: Party(kind="person", display_name="(unnamed)", email=value),
    )
    national_id = association_proxy(
        "party", "national_id",
        creator=lambda value: Party(kind="person", display_name="(unnamed)", national_id=value),
    )
    photo_url = association_proxy(
        "party", "photo_url",
        creator=lambda value: Party(kind="person", display_name="(unnamed)", photo_url=value),
    )


@event.listens_for(SASession, "before_flush")
def _pending_party_takes_the_persons_name(session, _ctx, _instances):
    """A party born from a proxy starts as "(unnamed)"; give it the name.

    The proxies' creators cannot see the person's name (the person may not
    even have one yet at that point), so a brand-new pair reaches the flush
    with the placeholder. The database trigger would fix the row anyway; this
    fixes the in-session object too, so code that reads ``display_name``
    right after creating a person sees what the database will hold.
    """
    for obj in session.new:
        if isinstance(obj, Person) and obj.party is not None and obj.party in session.new:
            display = " ".join(
                part
                for part in ((obj.first_name or "").strip(), (obj.last_name or "").strip())
                if part
            )
            if display:
                obj.party.display_name = display


@event.listens_for(Person, "before_insert")
def _person_creates_its_party(_mapper, connection, person):
    """Every new person gets a party row — the supertype half of ADR 0003.

    An ORM event rather than service code because persons are created in six
    application call sites and across the test suite; this is the one place
    they all pass through. Two ways a person can already have its party by the
    time this fires: a pending ``Party`` created by one of the association
    proxies flushed first (the relationship dependency orders it), or the
    caller wired ``party_id`` explicitly. Only a bare person — no proxy
    touched, no id given — needs the row created here. The display name is a
    placeholder either way; the ``trg_party_display_name`` trigger syncs it
    from the person's name the moment this insert lands.
    """
    if person.party_id is not None:
        return
    display_name = " ".join(
        part
        for part in ((person.first_name or "").strip(), (person.last_name or "").strip())
        if part
    )
    person.party_id = connection.execute(
        insert(Party.__table__)
        .values(kind="person", display_name=display_name or "(unnamed)")
        .returning(Party.__table__.c.id)
    ).scalar_one()


# The same trigger the repoint migration installs (29a3872dad10), attached to
# create_all so the test schema and a migrated database behave identically:
# party.display_name follows the person's name whoever writes it.
event.listen(
    Person.__table__,
    "after_create",
    DDL(
        """
CREATE OR REPLACE FUNCTION party_sync_display_name_from_person() RETURNS trigger AS $party_sync$
BEGIN
    UPDATE party
    SET display_name = btrim(coalesce(NEW.first_name, '') || ' ' || coalesce(NEW.last_name, '')),
        updated_at = now()
    WHERE id = NEW.party_id
      AND btrim(coalesce(NEW.first_name, '') || ' ' || coalesce(NEW.last_name, '')) <> '';
    RETURN NULL;
END;
$party_sync$ LANGUAGE plpgsql;

CREATE TRIGGER trg_party_display_name
    AFTER INSERT OR UPDATE OF first_name, last_name ON persons
    FOR EACH ROW EXECUTE FUNCTION party_sync_display_name_from_person();
        """
    ),
)


class Address(Base):
    """One owner, exactly, and a real one: the exclusive arc replaced the
    old ``entity_type``/``entity_id`` pair in Phase 3. A party address and a
    space address live in the same table because everything else about an
    address is identical; the CHECK is what keeps a row from floating free or
    serving two masters. The club's address is simply its party's address.
    """

    __tablename__ = "addresses"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(party_id, space_id) = 1",
            name="addresses_exactly_one_owner",
        ),
        Index("ix_addresses_party", "party_id", postgresql_where="party_id IS NOT NULL"),
        Index("ix_addresses_space", "space_id", postgresql_where="space_id IS NOT NULL"),
        # One primary address per party. The old nullable boolean let two rows
        # both claim it, and row order decided.
        Index(
            "uq_addresses_primary_per_party",
            "party_id",
            unique=True,
            postgresql_where="party_id IS NOT NULL AND is_primary",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    party_id = Column(
        BigInteger,
        ForeignKey("party.id", ondelete="CASCADE", name="addresses_party_id_fkey"),
    )
    space_id = Column(
        Integer,
        ForeignKey("spaces.id", ondelete="CASCADE", name="addresses_space_id_fkey"),
    )
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255))
    city = Column(String(100), nullable=False)
    state_province = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(3), default="ES")
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    is_primary = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    label = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    party = relationship("Party")
    person = relationship(
        "Person",
        back_populates="addresses",
        primaryjoin="Person.party_id == foreign(Address.party_id)",
        viewonly=True,
    )


class ContactChannel(Base):
    """What a contact value IS — email, phone, url, handle. Structural, where
    the old codes carried it only as a naming convention (``phone_*``,
    ``email_*``): "this party's email" was a LIKE against a code an admin
    could rename. A new channel is an INSERT here, same move as party_kinds.
    """

    __tablename__ = "contact_channels"

    code = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)


class ContactType(Base):
    __tablename__ = "contact_types"
    __table_args__ = (
        # Target of the composite FK on contacts: ties a contact's channel to
        # its type's channel so the two cannot disagree.
        UniqueConstraint("id", "channel", name="uq_contact_types_id_channel"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, unique=True)
    name = Column(String(50), nullable=False)
    description = Column(String(255))
    channel = Column(
        Text,
        ForeignKey("contact_channels.code", name="contact_types_channel_fkey"),
        nullable=False,
    )
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Contact(Base):
    """A way to reach a party. Single-owner since Phase 3: the old polymorphic
    CHECK only ever allowed ``'person'``, so this table paid the full price of
    polymorphism for one owner kind.

    ``channel`` is denormalised from the type on purpose. The composite FK
    keeps it honest, and it is what lets the partial unique below say "one
    primary per channel" — a primary email AND a primary phone, never two
    primary emails. A typeless contact has no channel (the CHECK ties the two
    nullabilities together), and the composite FK's SET NULL clears both when
    a type is deleted.
    """

    __tablename__ = "contacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["contact_type_id", "channel"],
            ["contact_types.id", "contact_types.channel"],
            name="contacts_channel_matches_type",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "(contact_type_id IS NULL) = (channel IS NULL)",
            name="contacts_channel_iff_type",
        ),
        Index("ix_contacts_party", "party_id"),
        Index("idx_contacts_type", "contact_type_id"),
        Index(
            "uq_contacts_one_primary_per_channel",
            "party_id",
            "channel",
            unique=True,
            postgresql_where="is_primary",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    party_id = Column(
        BigInteger,
        ForeignKey("party.id", ondelete="CASCADE", name="contacts_party_id_fkey"),
        nullable=False,
    )
    contact_type_id = Column(Integer)
    channel = Column(Text)
    value = Column(String(255), nullable=False)
    label = Column(String(100))
    is_primary = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    party = relationship("Party")
    contact_type = relationship(
        "ContactType",
        primaryjoin="foreign(Contact.contact_type_id) == ContactType.id",
        viewonly=True,
    )
    person = relationship(
        "Person",
        back_populates="contacts",
        primaryjoin="Person.party_id == foreign(Contact.party_id)",
        viewonly=True,
    )


@event.listens_for(Contact, "before_insert")
@event.listens_for(Contact, "before_update")
def _contact_carries_its_channel(_mapper, connection, contact):
    """Fill ``channel`` from the type so no call site has to know about it.

    The composite FK would reject a wrong value anyway; this makes the right
    one automatic. Runs on update too, so changing a contact's type cannot
    leave the old channel behind.
    """
    if contact.contact_type_id is None:
        contact.channel = None
        return
    contact.channel = connection.execute(
        ContactType.__table__.select()
        .with_only_columns(ContactType.__table__.c.channel)
        .where(ContactType.__table__.c.id == contact.contact_type_id)
    ).scalar_one_or_none()


@event.listens_for(SASession, "before_flush")
def _one_primary_contact_per_channel(session, _ctx, _instances):
    """Saving a contact as primary demotes the party's other primary in that
    channel, instead of colliding with ``uq_contacts_one_primary_per_channel``.

    Nothing demoted the incumbent before, and nothing caught the resulting
    ``IntegrityError``, so writes that had always worked became 500s: a channel
    holds several types (``phone_home``, ``phone_mobile``, ``phone_work`` and
    ``phone_emergency`` are all ``phone``), and a primary of each was legal
    until the index arrived. Four write paths reach this -- the two create
    endpoints, the update endpoint and the member's own profile -- so it lives
    here rather than at the call sites, which is also what makes it cover a
    writer nobody has added yet.

    Newest wins: the contact being saved takes the slot. The migration's dedupe
    keeps the *first* per channel instead, and the asymmetry is deliberate --
    at upgrade there is no user intent to read, here somebody ticked the box.

    ``channel`` is resolved from the type rather than read off the instance:
    ``_contact_carries_its_channel`` fills that column at ``before_insert``,
    which runs after this.
    """
    claiming = [
        obj
        for obj in list(session.new) + list(session.dirty)
        if isinstance(obj, Contact)
        and obj.is_primary
        and obj.party_id is not None
        and obj.contact_type_id is not None
    ]
    if not claiming:
        return

    with session.no_autoflush:
        for contact in claiming:
            channel = (
                session.query(ContactType.channel)
                .filter(ContactType.id == contact.contact_type_id)
                .scalar()
            )
            if channel is None:
                continue
            incumbents = session.query(Contact).filter(
                Contact.party_id == contact.party_id,
                Contact.channel == channel,
                Contact.is_primary.is_(True),
            )
            # A pending contact has no id to exclude itself by, and no row to
            # match either, so the filter is only needed for an update.
            if contact.id is not None:
                incumbents = incumbents.filter(Contact.id != contact.id)
            incumbents.update({"is_primary": False}, synchronize_session="fetch")
