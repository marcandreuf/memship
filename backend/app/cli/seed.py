"""CLI seed command — populates initial data for a fresh Memship installation.

Creates:
- Organization settings (defaults)
- Address types (home, work, billing, legal, venue)
- Contact types (phone_home, phone_mobile, phone_work, phone_emergency, email_work, email_other)
- Groups (Adult Members, Youth Programs, Senior Members, Honorary Members)
- Membership types (Full Member, Student, Family, Youth, Senior, Honorary)
- Admin accounts (interactive prompts or --test for test accounts)
- Sample activities with modalities and prices (--test only)
- Extra member accounts for realistic data (--test only)
- Sample registrations: confirmed, waitlisted, cancelled (--test only)
- Discount codes, consents, and attachment types per activity (--test only)

Usage:
    python -m app.cli.seed          # Interactive
    python -m app.cli.seed --test   # Test accounts + sample data
"""

import argparse
import getpass
import sys

from argon2 import PasswordHasher
from sqlalchemy import text

from app.db.session import SessionLocal
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import AddressType, ContactType, Person
from app.domains.auth.models import User
from app.domains.activities.models import (
    Activity, ActivityAttachmentType, ActivityConsent, ActivityModality,
    ActivityPrice, DiscountCode, Registration, RegistrationConsent,
)
from app.domains.members.models import Group, Member, MembershipType

ph = PasswordHasher()


def prompt_user_details(role_label: str) -> dict:
    print(f"\n--- {role_label} Account ---")
    first_name = input("First name: ").strip()
    last_name = input("Last name: ").strip()
    email = input("Email: ").strip()

    while True:
        password = getpass.getpass("Password (min 8 chars): ")
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            continue
        break

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "password": password,
    }


def seed_address_types(db) -> None:
    existing = db.query(AddressType).count()
    if existing > 0:
        print(f"  Address types: already seeded ({existing} records)")
        return

    types = [
        ("home", "Home", "Home address", 1),
        ("work", "Work", "Work address", 2),
        ("billing", "Billing", "Billing address", 3),
        ("legal", "Legal/Registered", "Legal or registered address", 4),
        ("venue", "Venue", "Venue or facility address", 5),
    ]
    for code, name, desc, order in types:
        db.add(AddressType(code=code, name=name, description=desc, display_order=order))
    db.flush()
    print(f"  Address types: created {len(types)} types")


def seed_contact_types(db) -> None:
    existing = db.query(ContactType).count()
    if existing > 0:
        print(f"  Contact types: already seeded ({existing} records)")
        return

    types = [
        ("phone_home", "Home Phone", "Home phone number", 1),
        ("phone_mobile", "Mobile Phone", "Mobile phone number", 2),
        ("phone_work", "Work Phone", "Work phone number", 3),
        ("phone_emergency", "Emergency Phone", "Emergency contact phone", 4),
        ("email_work", "Work Email", "Work email address", 5),
        ("email_other", "Other Email", "Other email address", 6),
    ]
    for code, name, desc, order in types:
        db.add(ContactType(code=code, name=name, description=desc, display_order=order))
    db.flush()
    print(f"  Contact types: created {len(types)} types")


def seed_org_settings(db) -> None:
    existing = db.query(OrganizationSettings).first()
    if existing:
        print(f"  Organization settings: already configured ({existing.name})")
        return

    org = OrganizationSettings(
        id=1,
        name="My Organization",
        locale="es",
        timezone="Europe/Madrid",
        currency="EUR",
        date_format="DD/MM/YYYY",
        features={},
        custom_settings={},
    )
    db.add(org)
    db.flush()
    print("  Organization settings: created with defaults")


def seed_groups(db) -> dict[str, Group]:
    existing = db.query(Group).count()
    if existing > 0:
        print(f"  Groups: already seeded ({existing} records)")
        groups = db.query(Group).all()
        return {g.slug: g for g in groups}

    group_data = [
        ("Adult Members", "adult-members", "Standard adult membership categories", True, "#4ECDC4", 1),
        ("Youth Programs", "youth-programs", "Programs and memberships for members under 18", True, "#FF6B6B", 2),
        ("Senior Members", "senior-members", "Memberships for members 65 and over", True, "#95A5C4", 3),
        ("Honorary Members", "honorary-members", "Non-paying honorary and lifetime memberships", False, "#F4D03F", 4),
    ]
    groups = {}
    for name, slug, desc, billable, color, order in group_data:
        g = Group(
            name=name, slug=slug, description=desc,
            is_billable=billable, color=color, display_order=order, is_active=True,
        )
        db.add(g)
        groups[slug] = g
    db.flush()
    print(f"  Groups: created {len(group_data)} groups")
    return groups


def seed_membership_types(db, groups: dict[str, Group]) -> MembershipType:
    existing = db.query(MembershipType).count()
    if existing > 0:
        default = db.query(MembershipType).filter_by(slug="full-member").first()
        if not default:
            default = db.query(MembershipType).first()
        print(f"  Membership types: already seeded ({existing} records)")
        return default

    adult_group = groups.get("adult-members")
    youth_group = groups.get("youth-programs")
    senior_group = groups.get("senior-members")
    honorary_group = groups.get("honorary-members")

    types = [
        MembershipType(
            name="Full Member", slug="full-member",
            description="Full membership with access to all facilities and voting rights",
            group_id=adult_group.id if adult_group else None,
            base_price=50.00, billing_frequency="monthly",
            display_order=1, is_active=True,
        ),
        MembershipType(
            name="Student", slug="student",
            description="Reduced rate for students with valid student ID",
            group_id=adult_group.id if adult_group else None,
            base_price=25.00, billing_frequency="monthly",
            min_age=16, max_age=25,
            display_order=2, is_active=True,
        ),
        MembershipType(
            name="Family", slug="family",
            description="Family plan covering up to 2 adults and 3 children under 18",
            group_id=adult_group.id if adult_group else None,
            base_price=90.00, billing_frequency="monthly",
            display_order=3, is_active=True,
        ),
        MembershipType(
            name="Youth", slug="youth",
            description="Membership for young members under 16",
            group_id=youth_group.id if youth_group else None,
            base_price=15.00, billing_frequency="monthly",
            max_age=15,
            display_order=4, is_active=True,
        ),
        MembershipType(
            name="Senior", slug="senior",
            description="Discounted rate for members aged 65 and over",
            group_id=senior_group.id if senior_group else None,
            base_price=30.00, billing_frequency="monthly",
            min_age=65,
            display_order=5, is_active=True,
        ),
        MembershipType(
            name="Honorary", slug="honorary",
            description="Complimentary lifetime membership granted by the board",
            group_id=honorary_group.id if honorary_group else None,
            base_price=0, billing_frequency="one_time",
            display_order=6, is_active=True,
        ),
    ]
    default = None
    for mt in types:
        db.add(mt)
        if mt.slug == "full-member":
            default = mt
    db.flush()
    print(f"  Membership types: created {len(types)} types")
    return default


def next_member_number(db) -> str:
    last = (
        db.query(Member)
        .filter(Member.member_number.isnot(None))
        .order_by(Member.id.desc())
        .first()
    )
    if last and last.member_number:
        try:
            num = int(last.member_number.replace("M-", ""))
            return f"M-{num + 1:04d}"
        except ValueError:
            pass
    return "M-0001"


def create_user_with_member(
    db, details: dict, role: str, membership_type: MembershipType
) -> None:
    existing = db.query(User).filter_by(email=details["email"]).first()
    if existing:
        print(f"  {role} user: already exists ({details['email']})")
        return

    person = Person(
        first_name=details["first_name"],
        last_name=details["last_name"],
        email=details["email"],
    )
    db.add(person)
    db.flush()

    user = User(
        person_id=person.id,
        email=details["email"],
        password_hash=ph.hash(details["password"]),
        role=role,
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    db.flush()

    member_number = next_member_number(db)
    member = Member(
        person_id=person.id,
        user_id=user.id,
        membership_type_id=membership_type.id,
        member_number=member_number,
        status="active",
    )
    db.add(member)
    db.flush()

    print(f"  {role} user: created ({details['email']}, member #{member_number})")


def seed_activities(db, user_id: int) -> None:
    existing = db.query(Activity).count()
    if existing > 0:
        print(f"  Activities: already seeded ({existing} records)")
        return

    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)

    activities_data = [
        {
            "name": "Summer Soccer Camp",
            "slug": "summer-soccer-camp",
            "description": "Week-long intensive soccer training for youth members. Professional coaches, daily matches, and skill workshops.",
            "short_description": "Intensive soccer training for youth",
            "starts_at": now + timedelta(days=90),
            "ends_at": now + timedelta(days=95),
            "registration_starts_at": now - timedelta(days=5),
            "registration_ends_at": now + timedelta(days=80),
            "location": "Main Stadium",
            "location_details": "Fields A and B, changing rooms available",
            "min_participants": 10,
            "max_participants": 30,
            "min_age": 6,
            "max_age": 17,
            "status": "published",
            "tax_rate": 21.00,
            "features": {"waiting_list": True},
            "allow_self_cancellation": True,
            "self_cancellation_deadline_hours": 48,
            "modalities": [
                {"name": "Morning Only", "description": "9:00 - 13:00", "max_participants": 15, "display_order": 1},
                {"name": "Full Day", "description": "9:00 - 17:00 (lunch included)", "max_participants": 15, "display_order": 2},
            ],
            "prices": [
                {"name": "Early Bird", "amount": 100.00, "is_default": False, "valid_from": now - timedelta(days=5), "valid_until": now + timedelta(days=30), "display_order": 1},
                {"name": "General", "amount": 150.00, "is_default": True, "valid_from": now + timedelta(days=30), "valid_until": now + timedelta(days=80), "display_order": 2},
            ],
        },
        {
            "name": "Yoga Workshop",
            "slug": "yoga-workshop",
            "description": "A relaxing weekend yoga workshop for all skill levels. Mats and equipment provided.",
            "short_description": "Weekend yoga for all levels",
            "starts_at": now + timedelta(days=45),
            "ends_at": now + timedelta(days=46),
            "registration_starts_at": now - timedelta(days=3),
            "registration_ends_at": now + timedelta(days=40),
            "location": "Wellness Center",
            "location_details": "Room 3, ground floor",
            "min_participants": 5,
            "max_participants": 20,
            "status": "published",
            "tax_rate": 10.00,
            "features": {"waiting_list": False},
            "allow_self_cancellation": True,
            "self_cancellation_deadline_hours": 24,
            "modalities": [],
            "prices": [
                {"name": "Member Price", "amount": 25.00, "is_default": True, "display_order": 1},
                {"name": "Non-Member", "amount": 40.00, "is_default": False, "is_optional": True, "display_order": 2},
            ],
        },
        {
            "name": "Annual Gala Dinner",
            "slug": "annual-gala-dinner",
            "description": "Join us for the annual gala dinner celebrating our community. Live music, awards ceremony, and three-course dinner.",
            "short_description": "Annual celebration with dinner and awards",
            "starts_at": now + timedelta(days=120),
            "ends_at": now + timedelta(days=120, hours=5),
            "registration_starts_at": now + timedelta(days=30),
            "registration_ends_at": now + timedelta(days=110),
            "location": "Grand Ballroom Hotel",
            "min_participants": 50,
            "max_participants": 200,
            "status": "draft",
            "tax_rate": 10.00,
            "features": {},
            "allow_self_cancellation": False,
            "modalities": [],
            "prices": [
                {"name": "Standard Ticket", "amount": 75.00, "is_default": True, "display_order": 1},
                {"name": "VIP Table (10 seats)", "amount": 650.00, "is_default": False, "display_order": 2},
            ],
        },
        {
            "name": "Photography Course",
            "slug": "photography-course",
            "description": "8-week photography course covering composition, lighting, and post-processing. Bring your own camera.",
            "short_description": "8-week course for beginners and intermediate",
            "starts_at": now + timedelta(days=60),
            "ends_at": now + timedelta(days=116),
            "registration_starts_at": now - timedelta(days=10),
            "registration_ends_at": now + timedelta(days=55),
            "location": "Art Studio",
            "location_details": "2nd floor, bring your own camera",
            "min_participants": 8,
            "max_participants": 15,
            "status": "published",
            "tax_rate": 21.00,
            "features": {"waiting_list": True},
            "allow_self_cancellation": True,
            "self_cancellation_deadline_hours": 72,
            "modalities": [
                {"name": "Weekday Evening", "description": "Tuesdays 18:00 - 20:00", "max_participants": 15, "display_order": 1},
                {"name": "Weekend Morning", "description": "Saturdays 10:00 - 12:00", "max_participants": 15, "display_order": 2},
            ],
            "prices": [
                {"name": "Full Course", "amount": 180.00, "is_default": True, "display_order": 1},
            ],
        },
    ]

    count = 0
    for act_data in activities_data:
        modalities_data = act_data.pop("modalities")
        prices_data = act_data.pop("prices")

        activity = Activity(**act_data, created_by=user_id)
        db.add(activity)
        db.flush()

        for mod_data in modalities_data:
            db.add(ActivityModality(activity_id=activity.id, **mod_data))
        db.flush()

        for price_data in prices_data:
            db.add(ActivityPrice(activity_id=activity.id, **price_data))
        db.flush()

        count += 1

    print(f"  Activities: created {count} activities with modalities and prices")


TEST_ACCOUNTS = [
    {
        "first_name": "Super",
        "last_name": "Admin",
        "email": "super@test.com",
        "password": "TestSuper1!",
        "role": "super_admin",
    },
    {
        "first_name": "Org",
        "last_name": "Admin",
        "email": "admin@test.com",
        "password": "TestAdmin1!",
        "role": "admin",
    },
    {
        "first_name": "Test",
        "last_name": "Member",
        "email": "member@test.com",
        "password": "TestMember1!",
        "role": "member",
    },
]

# Extra members for realistic registration data (--test only)
EXTRA_MEMBERS = [
    {"first_name": "María", "last_name": "García", "email": "maria@test.com", "date_of_birth": "1990-05-12"},
    {"first_name": "Joan", "last_name": "Puig", "email": "joan@test.com", "date_of_birth": "1985-11-03"},
    {"first_name": "Laura", "last_name": "Martínez", "email": "laura@test.com", "date_of_birth": "2000-08-22"},
    {"first_name": "Carlos", "last_name": "López", "email": "carlos@test.com", "date_of_birth": "1978-02-14"},
    {"first_name": "Anna", "last_name": "Ferrer", "email": "anna@test.com", "date_of_birth": "1995-07-30"},
]


def seed_extra_members(db, membership_type: MembershipType) -> list[Member]:
    """Create extra member accounts for realistic test data."""
    members = []
    for data in EXTRA_MEMBERS:
        existing = db.query(User).filter_by(email=data["email"]).first()
        if existing:
            member = db.query(Member).filter(Member.user_id == existing.id).first()
            if member:
                members.append(member)
            continue

        person = Person(
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            date_of_birth=data.get("date_of_birth"),
        )
        db.add(person)
        db.flush()

        user = User(
            person_id=person.id,
            email=data["email"],
            password_hash=ph.hash("TestMember1!"),
            role="member",
            is_active=True,
            email_verified=True,
        )
        db.add(user)
        db.flush()

        member_number = next_member_number(db)
        member = Member(
            person_id=person.id,
            user_id=user.id,
            membership_type_id=membership_type.id,
            member_number=member_number,
            status="active",
        )
        db.add(member)
        db.flush()
        members.append(member)

    if members:
        print(f"  Extra members: {len(members)} members ready")
    return members


def seed_registrations(db) -> None:
    """Create sample registrations across activities."""
    existing = db.query(Registration).count()
    if existing > 0:
        print(f"  Registrations: already seeded ({existing} records)")
        return

    from datetime import datetime, timezone

    # Get published activities and members
    activities = db.query(Activity).filter(Activity.status == "published").all()
    members = db.query(Member).filter(Member.status == "active").all()

    if len(activities) < 2 or len(members) < 3:
        print("  Registrations: not enough activities/members to seed")
        return

    count = 0
    cancelled_one = False

    for activity in activities:
        prices = db.query(ActivityPrice).filter(
            ActivityPrice.activity_id == activity.id,
            ActivityPrice.is_active.is_(True),
        ).all()
        if not prices:
            continue

        default_price = next((p for p in prices if p.is_default), prices[0])

        modalities = db.query(ActivityModality).filter(
            ActivityModality.activity_id == activity.id,
            ActivityModality.is_active.is_(True),
        ).all()

        # Register a subset of members for each activity
        members_to_register = members[:min(4, len(members))]

        for i, member in enumerate(members_to_register):
            # Check not already registered
            exists = db.query(Registration).filter(
                Registration.activity_id == activity.id,
                Registration.member_id == member.id,
            ).first()
            if exists:
                continue

            # Alternate modalities if available
            modality_id = modalities[i % len(modalities)].id if modalities else None

            # Determine status: most confirmed, last one waitlisted, one cancelled across all activities
            if i == len(members_to_register) - 1 and activity.features and activity.features.get("waiting_list"):
                status = "waitlist"
            elif not cancelled_one and i == len(members_to_register) - 2 and len(members_to_register) >= 3:
                status = "cancelled"
                cancelled_one = True
            else:
                status = "confirmed"

            reg = Registration(
                activity_id=activity.id,
                member_id=member.id,
                modality_id=modality_id,
                price_id=default_price.id,
                status=status,
                member_notes=f"Seeded registration #{count + 1}" if i == 0 else None,
            )
            if status == "cancelled":
                admin_user = db.query(User).filter_by(role="admin").first()
                reg.cancelled_at = datetime.now(timezone.utc)
                reg.cancelled_by = admin_user.id if admin_user else None
                reg.cancelled_reason = "Schedule conflict"

            db.add(reg)
            db.flush()

            # Update counters
            if status == "confirmed":
                activity.current_participants = (activity.current_participants or 0) + 1
                if modality_id:
                    mod = db.query(ActivityModality).filter(ActivityModality.id == modality_id).first()
                    if mod:
                        mod.current_participants = (mod.current_participants or 0) + 1
                default_price.current_registrations = (default_price.current_registrations or 0) + 1
            elif status == "waitlist":
                activity.waitlist_count = (activity.waitlist_count or 0) + 1

            count += 1

    db.flush()
    print(f"  Registrations: created {count} registrations (confirmed, waitlisted, cancelled)")


def seed_discount_codes(db) -> None:
    """Create sample discount codes for published activities."""
    existing = db.query(DiscountCode).count()
    if existing > 0:
        print(f"  Discount codes: already seeded ({existing} records)")
        return

    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)

    activities = db.query(Activity).filter(Activity.status == "published").all()
    count = 0

    for activity in activities:
        # Percentage code for every published activity
        db.add(DiscountCode(
            activity_id=activity.id,
            code="WELCOME10",
            description="Welcome discount — 10% off",
            discount_type="percentage",
            discount_value=10,
            max_uses=50,
            current_uses=0,
            valid_from=now - timedelta(days=5),
            valid_until=now + timedelta(days=180),
            is_active=True,
        ))
        count += 1

        # Fixed amount code for the first activity only
        if count == 1:
            db.add(DiscountCode(
                activity_id=activity.id,
                code="SUMMER25",
                description="Summer special — 25 EUR off",
                discount_type="fixed",
                discount_value=25,
                max_uses=10,
                current_uses=0,
                valid_from=now - timedelta(days=5),
                valid_until=now + timedelta(days=90),
                is_active=True,
            ))
            count += 1

            # Expired code for testing
            db.add(DiscountCode(
                activity_id=activity.id,
                code="EXPIRED5",
                description="Expired promo",
                discount_type="percentage",
                discount_value=5,
                max_uses=100,
                current_uses=3,
                valid_from=now - timedelta(days=60),
                valid_until=now - timedelta(days=1),
                is_active=True,
            ))
            count += 1

    db.flush()
    print(f"  Discount codes: created {count} codes across {len(activities)} activities")


def seed_consents(db) -> None:
    """Create sample activity consents for published activities."""
    existing = db.query(ActivityConsent).count()
    if existing > 0:
        print(f"  Activity consents: already seeded ({existing} records)")
        return

    activities = db.query(Activity).filter(Activity.status == "published").all()
    count = 0

    for activity in activities:
        # Mandatory liability waiver for every published activity
        db.add(ActivityConsent(
            activity_id=activity.id,
            title="Liability Waiver",
            content="I acknowledge that participation in this activity involves inherent risks. "
                    "I accept full responsibility for any injury or damage that may occur during the activity. "
                    "I release the organization and its staff from any liability.",
            is_mandatory=True,
            display_order=1,
            is_active=True,
        ))
        count += 1

        # Optional image rights consent
        db.add(ActivityConsent(
            activity_id=activity.id,
            title="Image Rights",
            content="I consent to the use of photographs and videos taken during this activity "
                    "for promotional purposes on the organization's website and social media channels.",
            is_mandatory=False,
            display_order=2,
            is_active=True,
        ))
        count += 1

    # Add a GDPR-style mandatory consent to the first activity
    if activities:
        db.add(ActivityConsent(
            activity_id=activities[0].id,
            title="Data Processing Consent",
            content="I consent to the processing of my personal data (name, contact information, "
                    "health-related data if applicable) for the purpose of managing my registration "
                    "and participation in this activity, in accordance with GDPR regulations.",
            is_mandatory=True,
            display_order=3,
            is_active=True,
        ))
        count += 1

    db.flush()
    print(f"  Activity consents: created {count} consents across {len(activities)} activities")


def seed_attachment_types(db) -> None:
    """Create sample attachment type requirements for published activities."""
    existing = db.query(ActivityAttachmentType).count()
    if existing > 0:
        print(f"  Attachment types: already seeded ({existing} records)")
        return

    activities = db.query(Activity).filter(Activity.status == "published").all()
    count = 0

    # Add medical certificate requirement to sport-related activities (first one)
    if activities:
        db.add(ActivityAttachmentType(
            activity_id=activities[0].id,
            name="Medical Certificate",
            description="A medical certificate confirming fitness to participate in physical activities. Must be issued within the last 12 months.",
            allowed_extensions=["pdf", "jpg", "jpeg", "png"],
            max_file_size_mb=5,
            is_mandatory=True,
            display_order=1,
            is_active=True,
        ))
        count += 1

        # Optional ID photo
        db.add(ActivityAttachmentType(
            activity_id=activities[0].id,
            name="ID Photo",
            description="A passport-style photo for the participant badge.",
            allowed_extensions=["jpg", "jpeg", "png"],
            max_file_size_mb=2,
            is_mandatory=False,
            display_order=2,
            is_active=True,
        ))
        count += 1

    # Add insurance document for any activity with modalities (likely sports)
    activities_with_modalities = [a for a in activities if db.query(ActivityModality).filter(
        ActivityModality.activity_id == a.id
    ).count() > 0]

    for activity in activities_with_modalities[1:2]:  # second modality-based activity if exists
        db.add(ActivityAttachmentType(
            activity_id=activity.id,
            name="Insurance Document",
            description="Proof of personal liability insurance or sports insurance.",
            allowed_extensions=["pdf"],
            max_file_size_mb=5,
            is_mandatory=True,
            display_order=1,
            is_active=True,
        ))
        count += 1

    db.flush()
    print(f"  Attachment types: created {count} types across published activities")


def seed_registration_consents(db) -> None:
    """Create consent acceptances for existing registrations."""
    existing = db.query(RegistrationConsent).count()
    if existing > 0:
        print(f"  Registration consents: already seeded ({existing} records)")
        return

    registrations = db.query(Registration).filter(
        Registration.status.in_(["confirmed", "waitlist"])
    ).all()

    count = 0
    for reg in registrations:
        consents = db.query(ActivityConsent).filter(
            ActivityConsent.activity_id == reg.activity_id,
            ActivityConsent.is_active.is_(True),
        ).all()

        for consent in consents:
            # Accept all mandatory consents; accept optional ones ~50% of the time
            accept = consent.is_mandatory or (reg.id % 2 == 0)
            db.add(RegistrationConsent(
                registration_id=reg.id,
                activity_consent_id=consent.id,
                accepted=accept,
            ))
            count += 1

    db.flush()
    print(f"  Registration consents: created {count} consent records for existing registrations")


def main() -> None:
    parser = argparse.ArgumentParser(description="Memship seed command")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Create test accounts with simple passwords instead of interactive prompts",
    )
    args = parser.parse_args()

    print("\n=== Memship Seed ===\n")
    print("This will set up initial data for a fresh installation.")
    print("If data already exists, existing records will be skipped.\n")

    db = SessionLocal()
    try:
        # Check database connectivity
        db.execute(text("SELECT 1"))
        print("Database connection: OK\n")

        print("Seeding lookup tables...")
        seed_address_types(db)
        seed_contact_types(db)

        print("\nSeeding organization...")
        seed_org_settings(db)

        print("\nSeeding groups...")
        groups = seed_groups(db)

        print("\nSeeding membership types...")
        membership_type = seed_membership_types(db, groups)

        if args.test:
            print("\nCreating test accounts...")
            for account in TEST_ACCOUNTS:
                create_user_with_member(
                    db,
                    account,
                    account["role"],
                    membership_type,
                )
            # Seed activities (need a user_id for created_by)
            admin_user = db.query(User).filter_by(email="admin@test.com").first()
            if admin_user:
                print("\nSeeding activities...")
                seed_activities(db, admin_user.id)

            print("\nSeeding extra members...")
            seed_extra_members(db, membership_type)

            print("\nSeeding registrations...")
            seed_registrations(db)

            print("\nSeeding discount codes...")
            seed_discount_codes(db)

            print("\nSeeding activity consents...")
            seed_consents(db)

            print("\nSeeding attachment types...")
            seed_attachment_types(db)

            print("\nSeeding registration consents...")
            seed_registration_consents(db)

            print("\n  ⚠  TEST ACCOUNTS — do NOT use in production:")
            for account in TEST_ACCOUNTS:
                print(f"     {account['role']:15s} {account['email']:25s} / {account['password']}")
            print(f"     {'member':15s} {'(+5 extra members)':25s} / TestMember1!")
        else:
            # Interactive user creation
            super_admin = prompt_user_details("Super Admin")
            create_user_with_member(db, super_admin, "super_admin", membership_type)

            org_admin = prompt_user_details("Organization Admin")
            create_user_with_member(db, org_admin, "admin", membership_type)

        db.commit()
        print("\n=== Seed complete ===\n")

    except KeyboardInterrupt:
        db.rollback()
        print("\n\nSeed cancelled.")
        sys.exit(1)
    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
