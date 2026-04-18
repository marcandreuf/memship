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
- SEPA mandates, payment provider, and batchable receipts (--test only)

Usage:
    python -m app.cli.seed          # Interactive
    python -m app.cli.seed --test   # Test accounts + sample data
"""

import argparse
import getpass
import sys
from pathlib import Path

from argon2 import PasswordHasher
from sqlalchemy import text

from app.db.session import SessionLocal
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Address, AddressType, Contact, ContactType, Person
from app.domains.auth.models import User
from app.domains.activities.models import (
    Activity, ActivityAttachmentType, ActivityConsent, ActivityModality,
    ActivityPrice, DiscountCode, Registration, RegistrationConsent,
)
from app.domains.members.models import Group, Member, MembershipType
from app.domains.billing.models import Concept, PaymentProvider, Receipt, Remittance, SepaMandate

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
        name="Club Esportiu Mediterrani",
        legal_name="Club Esportiu Mediterrani S.L.",
        email="info@cemediterrani.cat",
        phone="+34 933 001 234",
        website="https://cemediterrani.cat",
        tax_id="B12345678",
        locale="es",
        timezone="Europe/Madrid",
        currency="EUR",
        date_format="DD/MM/YYYY",
        brand_color="#0083ad",
        bank_name="CaixaBank",
        bank_iban="ES9121000418450200051332",
        bank_bic="CAIXESBBXXX",
        invoice_prefix="FAC",
        invoice_next_number=1,
        invoice_annual_reset=True,
        default_vat_rate=21.00,
        features={
            "gender_options": [
                {"value": "male", "label_es": "Hombre", "label_ca": "Home", "label_en": "Male"},
                {"value": "female", "label_es": "Mujer", "label_ca": "Dona", "label_en": "Female"},
                {"value": "non_binary", "label_es": "No binario", "label_ca": "No binari", "label_en": "Non-binary"},
                {"value": "other", "label_es": "Otro", "label_ca": "Altre", "label_en": "Other"},
                {"value": "prefer_not_to_say", "label_es": "Prefiero no decirlo", "label_ca": "Prefereixo no dir-ho", "label_en": "Prefer not to say"},
            ],
        },
        custom_settings={},
    )
    db.add(org)
    db.flush()

    # Add organization address
    legal_type = db.query(AddressType).filter(AddressType.code == "legal").first()
    org_address = Address(
        entity_type="organization",
        entity_id=1,
        address_type_id=legal_type.id if legal_type else None,
        address_line1="Carrer de la Marina 22",
        address_line2="Local 3",
        city="Barcelona",
        state_province="Barcelona",
        postal_code="08005",
        country="ES",
        is_primary=True,
    )
    db.add(org_address)
    db.flush()

    print("  Organization settings: created 'Club Esportiu Mediterrani' (address + bank details)")


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
        # --- Published activities with open registration ---
        {"name": "Summer Soccer Camp", "slug": "summer-soccer-camp", "short_description": "Intensive soccer training for youth", "description": "Week-long intensive soccer training for youth members. Professional coaches, daily matches, and skill workshops.", "starts_at": now + timedelta(days=90), "ends_at": now + timedelta(days=95), "registration_starts_at": now - timedelta(days=5), "registration_ends_at": now + timedelta(days=80), "location": "Main Stadium", "location_details": "Fields A and B", "min_participants": 10, "max_participants": 30, "min_age": 6, "max_age": 17, "status": "published", "tax_rate": 21.00, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 48,
            "modalities": [{"name": "Morning Only", "description": "9:00 - 13:00", "max_participants": 15, "display_order": 1}, {"name": "Full Day", "description": "9:00 - 17:00", "max_participants": 15, "display_order": 2}],
            "prices": [{"name": "Early Bird", "amount": 100.00, "is_default": False, "valid_from": now - timedelta(days=5), "valid_until": now + timedelta(days=30), "display_order": 1}, {"name": "General", "amount": 150.00, "is_default": True, "valid_from": now + timedelta(days=30), "valid_until": now + timedelta(days=80), "display_order": 2}]},
        {"name": "Yoga Workshop", "slug": "yoga-workshop", "short_description": "Weekend yoga for all levels", "description": "A relaxing weekend yoga workshop for all skill levels. Mats and equipment provided.", "starts_at": now + timedelta(days=45), "ends_at": now + timedelta(days=46), "registration_starts_at": now - timedelta(days=3), "registration_ends_at": now + timedelta(days=40), "location": "Wellness Center", "min_participants": 5, "max_participants": 20, "status": "published", "tax_rate": 10.00, "features": {"waiting_list": False}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 24,
            "modalities": [],
            "prices": [{"name": "Member Price", "amount": 25.00, "is_default": True, "display_order": 1}]},
        {"name": "Photography Course", "slug": "photography-course", "short_description": "8-week course for beginners", "description": "Photography course covering composition, lighting, and post-processing.", "starts_at": now + timedelta(days=60), "ends_at": now + timedelta(days=116), "registration_starts_at": now - timedelta(days=10), "registration_ends_at": now + timedelta(days=55), "location": "Art Studio", "min_participants": 8, "max_participants": 15, "status": "published", "tax_rate": 21.00, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 72,
            "modalities": [{"name": "Weekday Evening", "description": "Tuesdays 18:00 - 20:00", "max_participants": 15, "display_order": 1}, {"name": "Weekend Morning", "description": "Saturdays 10:00 - 12:00", "max_participants": 15, "display_order": 2}],
            "prices": [{"name": "Full Course", "amount": 180.00, "is_default": True, "display_order": 1}]},
        {"name": "Swimming Lessons", "slug": "swimming-lessons", "short_description": "Learn to swim — all ages", "description": "Swimming lessons for beginners and intermediate swimmers. Certified instructors.", "starts_at": now + timedelta(days=30), "ends_at": now + timedelta(days=90), "registration_starts_at": now - timedelta(days=7), "registration_ends_at": now + timedelta(days=25), "location": "Municipal Pool", "min_participants": 6, "max_participants": 12, "status": "published", "tax_rate": 10.00, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 24,
            "modalities": [{"name": "Children (6-12)", "description": "Sat 10:00 - 11:00", "max_participants": 6, "display_order": 1}, {"name": "Adults", "description": "Sat 11:00 - 12:00", "max_participants": 6, "display_order": 2}],
            "prices": [{"name": "Monthly", "amount": 35.00, "is_default": True, "display_order": 1}]},
        {"name": "Cooking Class: Mediterranean", "slug": "cooking-mediterranean", "short_description": "Traditional Mediterranean cuisine", "description": "Hands-on cooking class featuring traditional Mediterranean recipes. Ingredients included.", "starts_at": now + timedelta(days=21), "ends_at": now + timedelta(days=21, hours=4), "registration_starts_at": now - timedelta(days=14), "registration_ends_at": now + timedelta(days=18), "location": "Community Kitchen", "min_participants": 8, "max_participants": 16, "status": "published", "tax_rate": 10.00, "features": {}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 48,
            "modalities": [],
            "prices": [{"name": "Per Person", "amount": 45.00, "is_default": True, "display_order": 1}]},
        {"name": "Tennis Tournament", "slug": "tennis-tournament", "short_description": "Singles and doubles brackets", "description": "Annual club tennis tournament. Singles and doubles categories. Trophies and prizes.", "starts_at": now + timedelta(days=75), "ends_at": now + timedelta(days=77), "registration_starts_at": now - timedelta(days=2), "registration_ends_at": now + timedelta(days=65), "location": "Tennis Courts", "min_participants": 16, "max_participants": 32, "min_age": 14, "status": "published", "tax_rate": 21.00, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 72,
            "modalities": [{"name": "Singles", "max_participants": 16, "display_order": 1}, {"name": "Doubles", "max_participants": 16, "display_order": 2}],
            "prices": [{"name": "Entry Fee", "amount": 20.00, "is_default": True, "display_order": 1}]},
        {"name": "Art Exhibition Opening", "slug": "art-exhibition-opening", "short_description": "Members art showcase", "description": "Opening night of the annual members art exhibition. Wine reception and guided tour.", "starts_at": now + timedelta(days=40), "ends_at": now + timedelta(days=40, hours=3), "registration_starts_at": now - timedelta(days=7), "registration_ends_at": now + timedelta(days=38), "location": "Gallery Hall", "min_participants": 20, "max_participants": 80, "status": "published", "tax_rate": 0, "features": {}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 24,
            "modalities": [],
            "prices": [{"name": "Free Entry", "amount": 0, "is_default": True, "display_order": 1}]},
        {"name": "First Aid Certification", "slug": "first-aid-certification", "short_description": "Official first aid course", "description": "Two-day certified first aid course. Certificate valid for 2 years.", "starts_at": now + timedelta(days=50), "ends_at": now + timedelta(days=51), "registration_starts_at": now - timedelta(days=5), "registration_ends_at": now + timedelta(days=45), "location": "Training Room B", "min_participants": 10, "max_participants": 20, "min_age": 16, "status": "published", "tax_rate": 0, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 48,
            "modalities": [],
            "prices": [{"name": "Course Fee", "amount": 60.00, "is_default": True, "display_order": 1}]},
        {"name": "Kids Dance Party", "slug": "kids-dance-party", "short_description": "Fun dance event for children", "description": "Afternoon dance party with DJ, games, and snacks for kids.", "starts_at": now + timedelta(days=14), "ends_at": now + timedelta(days=14, hours=3), "registration_starts_at": now - timedelta(days=10), "registration_ends_at": now + timedelta(days=12), "location": "Main Hall", "min_participants": 15, "max_participants": 50, "max_age": 12, "status": "published", "tax_rate": 0, "features": {}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 24,
            "modalities": [],
            "prices": [{"name": "Entry", "amount": 5.00, "is_default": True, "display_order": 1}]},
        {"name": "Book Club: Spring Edition", "slug": "book-club-spring", "short_description": "Monthly book discussions", "description": "Join our book club for monthly discussions. April-June reading list.", "starts_at": now + timedelta(days=35), "ends_at": now + timedelta(days=95), "registration_starts_at": now - timedelta(days=5), "registration_ends_at": now + timedelta(days=30), "location": "Library Room", "min_participants": 5, "max_participants": 15, "status": "published", "tax_rate": 0, "features": {}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 24,
            "modalities": [],
            "prices": [{"name": "Free", "amount": 0, "is_default": True, "display_order": 1}]},
        {"name": "Mountain Hiking Trip", "slug": "mountain-hiking-trip", "short_description": "Guided hike to Montserrat", "description": "Full-day guided hiking trip to Montserrat. Transport and picnic lunch included.", "starts_at": now + timedelta(days=55), "ends_at": now + timedelta(days=55, hours=10), "registration_starts_at": now - timedelta(days=3), "registration_ends_at": now + timedelta(days=50), "location": "Montserrat Natural Park", "min_participants": 10, "max_participants": 25, "min_age": 12, "status": "published", "tax_rate": 10.00, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 48,
            "modalities": [{"name": "Easy Route", "description": "5km, 300m elevation", "max_participants": 15, "display_order": 1}, {"name": "Advanced Route", "description": "12km, 800m elevation", "max_participants": 10, "display_order": 2}],
            "prices": [{"name": "Per Person", "amount": 30.00, "is_default": True, "display_order": 1}]},
        {"name": "Chess Club Tournament", "slug": "chess-club-tournament", "short_description": "Monthly rated tournament", "description": "Monthly chess tournament with Swiss pairing. All levels welcome.", "starts_at": now + timedelta(days=28), "ends_at": now + timedelta(days=28, hours=5), "registration_starts_at": now - timedelta(days=10), "registration_ends_at": now + timedelta(days=25), "location": "Games Room", "min_participants": 8, "max_participants": 24, "status": "published", "tax_rate": 0, "features": {"waiting_list": False}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 24,
            "modalities": [],
            "prices": [{"name": "Entry Fee", "amount": 5.00, "is_default": True, "display_order": 1}]},
        {"name": "Spanish Guitar Workshop", "slug": "spanish-guitar-workshop", "short_description": "Classical guitar for beginners", "description": "Learn the basics of classical Spanish guitar. Guitars available for loan.", "starts_at": now + timedelta(days=42), "ends_at": now + timedelta(days=84), "registration_starts_at": now - timedelta(days=5), "registration_ends_at": now + timedelta(days=38), "location": "Music Room", "min_participants": 4, "max_participants": 10, "status": "published", "tax_rate": 21.00, "features": {}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 48,
            "modalities": [],
            "prices": [{"name": "6-Week Course", "amount": 120.00, "is_default": True, "display_order": 1}]},
        {"name": "Beach Volleyball League", "slug": "beach-volleyball-league", "short_description": "Summer beach volleyball", "description": "Weekly beach volleyball league. Teams of 4. June through August.", "starts_at": now + timedelta(days=80), "ends_at": now + timedelta(days=170), "registration_starts_at": now - timedelta(days=5), "registration_ends_at": now + timedelta(days=70), "location": "Beach Courts", "min_participants": 16, "max_participants": 40, "min_age": 16, "status": "published", "tax_rate": 10.00, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 72,
            "modalities": [{"name": "Competitive", "max_participants": 20, "display_order": 1}, {"name": "Recreational", "max_participants": 20, "display_order": 2}],
            "prices": [{"name": "Season Pass", "amount": 50.00, "is_default": True, "display_order": 1}]},
        {"name": "Pottery Workshop", "slug": "pottery-workshop", "short_description": "Hands-on ceramics class", "description": "Learn wheel throwing and hand building techniques. All materials included.", "starts_at": now + timedelta(days=35), "ends_at": now + timedelta(days=63), "registration_starts_at": now - timedelta(days=7), "registration_ends_at": now + timedelta(days=30), "location": "Craft Studio", "min_participants": 4, "max_participants": 8, "status": "published", "tax_rate": 21.00, "features": {}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 48,
            "modalities": [],
            "prices": [{"name": "4-Week Course", "amount": 95.00, "is_default": True, "display_order": 1}]},
        # --- Published: registration NOT YET OPEN ---
        {"name": "New Year's Gala 2027", "slug": "new-years-gala-2027", "short_description": "Ring in 2027 with style", "description": "Exclusive New Year's Eve gala with live music, dinner, and champagne toast at midnight.", "starts_at": now + timedelta(days=280), "ends_at": now + timedelta(days=280, hours=6), "registration_starts_at": now + timedelta(days=200), "registration_ends_at": now + timedelta(days=270), "location": "Grand Ballroom", "min_participants": 50, "max_participants": 200, "status": "published", "tax_rate": 10.00, "features": {}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 72,
            "modalities": [],
            "prices": [{"name": "Standard Ticket", "amount": 85.00, "is_default": True, "display_order": 1}, {"name": "VIP Table (8 seats)", "amount": 600.00, "is_default": False, "display_order": 2}]},
        {"name": "Autumn Photography Retreat", "slug": "autumn-photography-retreat", "short_description": "Weekend retreat in the countryside", "description": "Three-day photography retreat focusing on autumn landscapes. Accommodation and meals included.", "starts_at": now + timedelta(days=210), "ends_at": now + timedelta(days=213), "registration_starts_at": now + timedelta(days=120), "registration_ends_at": now + timedelta(days=200), "location": "Rural Retreat Center", "min_participants": 8, "max_participants": 16, "status": "published", "tax_rate": 10.00, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 168,
            "modalities": [],
            "prices": [{"name": "Full Package", "amount": 320.00, "is_default": True, "display_order": 1}]},
        # --- Published: registration open but FULL (tiny capacity, filled by seed registrations) ---
        {"name": "Private Wine Tasting", "slug": "private-wine-tasting", "short_description": "Exclusive wine tasting evening", "description": "Intimate wine tasting session with sommelier. Very limited capacity.", "starts_at": now + timedelta(days=25), "ends_at": now + timedelta(days=25, hours=3), "registration_starts_at": now - timedelta(days=10), "registration_ends_at": now + timedelta(days=20), "location": "Wine Cellar", "min_participants": 1, "max_participants": 2, "status": "published", "tax_rate": 10.00, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 48,
            "modalities": [],
            "prices": [{"name": "Per Person", "amount": 55.00, "is_default": True, "display_order": 1}]},
        # --- Published: registration CLOSED ---
        {"name": "Spring Marathon 2026", "slug": "spring-marathon-2026", "short_description": "10K and half-marathon", "description": "Annual spring marathon through the city center. 10K and half-marathon distances available.", "starts_at": now + timedelta(days=10), "ends_at": now + timedelta(days=10, hours=6), "registration_starts_at": now - timedelta(days=60), "registration_ends_at": now - timedelta(days=5), "location": "City Center", "min_participants": 50, "max_participants": 500, "status": "published", "tax_rate": 0, "features": {}, "allow_self_cancellation": False,
            "modalities": [{"name": "10K", "max_participants": 300, "display_order": 1}, {"name": "Half Marathon", "max_participants": 200, "display_order": 2}],
            "prices": [{"name": "Entry Fee", "amount": 25.00, "is_default": True, "display_order": 1}]},
        {"name": "Easter Egg Hunt", "slug": "easter-egg-hunt-2026", "short_description": "Family fun egg hunt", "description": "Annual Easter egg hunt in the park. Prizes for all age categories.", "starts_at": now + timedelta(days=5), "ends_at": now + timedelta(days=5, hours=3), "registration_starts_at": now - timedelta(days=30), "registration_ends_at": now - timedelta(days=2), "location": "Central Park", "max_age": 14, "min_participants": 20, "max_participants": 80, "status": "published", "tax_rate": 0, "features": {}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 24,
            "modalities": [],
            "prices": [{"name": "Free", "amount": 0, "is_default": True, "display_order": 1}]},
        # --- Draft activities ---
        {"name": "Annual Gala Dinner", "slug": "annual-gala-dinner", "short_description": "Annual celebration with dinner and awards", "description": "Join us for the annual gala dinner. Live music, awards ceremony, and three-course dinner.", "starts_at": now + timedelta(days=120), "ends_at": now + timedelta(days=120, hours=5), "registration_starts_at": now + timedelta(days=30), "registration_ends_at": now + timedelta(days=110), "location": "Grand Ballroom Hotel", "min_participants": 50, "max_participants": 200, "status": "draft", "tax_rate": 10.00, "features": {}, "allow_self_cancellation": False,
            "modalities": [],
            "prices": [{"name": "Standard Ticket", "amount": 75.00, "is_default": True, "display_order": 1}, {"name": "VIP Table (10 seats)", "amount": 650.00, "is_default": False, "display_order": 2}]},
        {"name": "Halloween Party", "slug": "halloween-party", "short_description": "Costume party for all ages", "description": "Annual Halloween costume party with prizes, music, and themed food.", "starts_at": now + timedelta(days=200), "ends_at": now + timedelta(days=200, hours=5), "registration_starts_at": now + timedelta(days=150), "registration_ends_at": now + timedelta(days=195), "location": "Main Hall", "min_participants": 30, "max_participants": 100, "status": "draft", "tax_rate": 10.00, "features": {}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 24,
            "modalities": [],
            "prices": [{"name": "Entry", "amount": 10.00, "is_default": True, "display_order": 1}]},
        {"name": "Winter Skiing Trip", "slug": "winter-skiing-trip", "short_description": "Weekend ski trip to Pyrenees", "description": "Two-day skiing trip with transport, accommodation, and ski pass.", "starts_at": now + timedelta(days=250), "ends_at": now + timedelta(days=252), "registration_starts_at": now + timedelta(days=180), "registration_ends_at": now + timedelta(days=240), "location": "La Molina Ski Resort", "min_participants": 20, "max_participants": 45, "min_age": 10, "status": "draft", "tax_rate": 10.00, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 72,
            "modalities": [{"name": "Beginner Package", "description": "Includes equipment rental and lessons", "max_participants": 20, "display_order": 1}, {"name": "Experienced", "description": "Ski pass only", "max_participants": 25, "display_order": 2}],
            "prices": [{"name": "Full Package", "amount": 250.00, "is_default": True, "display_order": 1}, {"name": "Transport Only", "amount": 80.00, "is_default": False, "display_order": 2}]},
        {"name": "Summer Camp 2027", "slug": "summer-camp-2027", "short_description": "Two-week youth summer camp", "description": "Full summer camp program with sports, arts, and outdoor activities.", "starts_at": now + timedelta(days=300), "ends_at": now + timedelta(days=314), "registration_starts_at": now + timedelta(days=200), "registration_ends_at": now + timedelta(days=285), "location": "Camp Grounds", "min_participants": 30, "max_participants": 60, "min_age": 8, "max_age": 16, "status": "draft", "tax_rate": 10.00, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 168,
            "modalities": [{"name": "Week 1 Only", "max_participants": 60, "display_order": 1}, {"name": "Week 2 Only", "max_participants": 60, "display_order": 2}, {"name": "Both Weeks", "max_participants": 40, "display_order": 3}],
            "prices": [{"name": "One Week", "amount": 350.00, "is_default": True, "display_order": 1}, {"name": "Two Weeks", "amount": 600.00, "is_default": False, "display_order": 2}]},
        # --- Archived/cancelled activities ---
        {"name": "Spring 5K Run", "slug": "spring-5k-run", "short_description": "Community fun run", "description": "Annual spring 5K run through the park. Medals for all finishers.", "starts_at": now - timedelta(days=30), "ends_at": now - timedelta(days=30, hours=-3), "registration_starts_at": now - timedelta(days=90), "registration_ends_at": now - timedelta(days=35), "location": "City Park", "min_participants": 20, "max_participants": 100, "status": "archived", "tax_rate": 0, "features": {}, "allow_self_cancellation": False,
            "modalities": [],
            "prices": [{"name": "Registration", "amount": 15.00, "is_default": True, "display_order": 1}]},
        {"name": "Winter Concert", "slug": "winter-concert", "short_description": "Holiday music concert", "description": "End-of-year concert featuring the club choir and guest musicians.", "starts_at": now - timedelta(days=90), "ends_at": now - timedelta(days=90, hours=-3), "registration_starts_at": now - timedelta(days=150), "registration_ends_at": now - timedelta(days=95), "location": "Auditorium", "min_participants": 30, "max_participants": 150, "status": "archived", "tax_rate": 0, "features": {}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 24,
            "modalities": [],
            "prices": [{"name": "Free Entry", "amount": 0, "is_default": True, "display_order": 1}]},
        {"name": "Indoor Basketball League", "slug": "indoor-basketball-cancelled", "short_description": "Weekly basketball league", "description": "Indoor basketball league cancelled due to facility renovation.", "starts_at": now + timedelta(days=60), "ends_at": now + timedelta(days=150), "registration_starts_at": now - timedelta(days=30), "registration_ends_at": now + timedelta(days=50), "location": "Sports Hall", "min_participants": 20, "max_participants": 40, "status": "cancelled", "tax_rate": 10.00, "features": {"waiting_list": True}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 48,
            "modalities": [],
            "prices": [{"name": "Season Pass", "amount": 40.00, "is_default": True, "display_order": 1}]},
        {"name": "Painting Workshop: Watercolors", "slug": "painting-watercolors-cancelled", "short_description": "Watercolor techniques", "description": "Cancelled — instructor unavailable. Will be rescheduled.", "starts_at": now + timedelta(days=20), "ends_at": now + timedelta(days=48), "registration_starts_at": now - timedelta(days=20), "registration_ends_at": now + timedelta(days=15), "location": "Art Studio", "min_participants": 6, "max_participants": 12, "status": "cancelled", "tax_rate": 21.00, "features": {}, "allow_self_cancellation": True, "self_cancellation_deadline_hours": 24,
            "modalities": [],
            "prices": [{"name": "Course Fee", "amount": 85.00, "is_default": True, "display_order": 1}]},
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

    # Set sample cover image for Summer Soccer Camp
    _seed_sample_cover_image(db)

    print(f"  Activities: created {count} activities with modalities and prices")


def _seed_sample_cover_image(db) -> None:
    """Copy sample cover image to storage for Summer Soccer Camp."""
    import shutil

    fixtures_dir = Path(__file__).parent / "fixtures"
    sample_image = fixtures_dir / "summer camp.jpeg"
    if not sample_image.exists():
        return

    soccer_camp = db.query(Activity).filter(Activity.slug == "summer-soccer-camp").first()
    if not soccer_camp or soccer_camp.image_url:
        return

    from app.core.config import settings

    storage_dir = Path(settings.STORAGE_LOCAL_PATH) / "activities" / str(soccer_camp.id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    dest = storage_dir / "cover.jpeg"
    shutil.copy2(str(sample_image), str(dest))

    soccer_camp.image_url = f"/uploads/activities/{soccer_camp.id}/cover.jpeg"
    db.flush()
    print(f"  Cover image: set for '{soccer_camp.name}'")


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
    {"first_name": "Marta", "last_name": "Soler", "email": "marta@test.com", "date_of_birth": "1992-01-18"},
    {"first_name": "Jordi", "last_name": "Vidal", "email": "jordi@test.com", "date_of_birth": "1988-09-25"},
    {"first_name": "Elena", "last_name": "Ruiz", "email": "elena@test.com", "date_of_birth": "1997-03-07"},
    {"first_name": "Àlex", "last_name": "Serra", "email": "alex@test.com", "date_of_birth": "2001-06-14"},
    {"first_name": "Nuria", "last_name": "Blanch", "email": "nuria@test.com", "date_of_birth": "1983-12-02"},
    {"first_name": "Marc", "last_name": "Roca", "email": "marc@test.com", "date_of_birth": "1975-04-19"},
    {"first_name": "Carla", "last_name": "Pons", "email": "carla@test.com", "date_of_birth": "1999-10-08"},
    {"first_name": "Pau", "last_name": "Mas", "email": "pau@test.com", "date_of_birth": "1991-07-21"},
    {"first_name": "Laia", "last_name": "Font", "email": "laia@test.com", "date_of_birth": "1986-02-28"},
    {"first_name": "Oriol", "last_name": "Casals", "email": "oriol@test.com", "date_of_birth": "1994-11-15"},
    {"first_name": "Gemma", "last_name": "Rovira", "email": "gemma@test.com", "date_of_birth": "1980-08-04"},
    {"first_name": "Arnau", "last_name": "Bosch", "email": "arnau@test.com", "date_of_birth": "2002-01-30"},
    {"first_name": "Sílvia", "last_name": "Esteve", "email": "silvia@test.com", "date_of_birth": "1993-05-22"},
    {"first_name": "David", "last_name": "Navarro", "email": "david@test.com", "date_of_birth": "1976-09-11"},
    {"first_name": "Montse", "last_name": "Costa", "email": "montse@test.com", "date_of_birth": "1989-04-03"},
    {"first_name": "Ferran", "last_name": "Aguilar", "email": "ferran@test.com", "date_of_birth": "1998-12-17"},
    {"first_name": "Aina", "last_name": "Torrent", "email": "aina@test.com", "date_of_birth": "1984-06-09"},
]


def seed_extra_members(db, default_membership_type: MembershipType) -> list[Member]:
    """Create extra member accounts for realistic test data."""
    # Get all membership types for variety
    all_types = db.query(MembershipType).filter(MembershipType.is_active.is_(True)).all()
    type_ids = [mt.id for mt in all_types] if all_types else [default_membership_type.id]

    # Assign varied statuses for realism
    statuses = ["active"] * 16 + ["pending"] * 3 + ["suspended"] * 1 + ["expired"] * 2

    members = []
    for i, data in enumerate(EXTRA_MEMBERS):
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
        status = statuses[i % len(statuses)]
        member = Member(
            person_id=person.id,
            user_id=user.id,
            membership_type_id=type_ids[i % len(type_ids)],
            member_number=member_number,
            status=status,
        )
        db.add(member)
        db.flush()
        members.append(member)

    if members:
        print(f"  Extra members: {len(members)} members ready")
    return members


def seed_member_contacts(db) -> None:
    """Add sample contacts and bank IBANs for test members."""
    mobile_type = db.query(ContactType).filter(ContactType.code == "phone_mobile").first()
    work_email_type = db.query(ContactType).filter(ContactType.code == "email_work").first()

    # Sample contacts for a few members
    contact_data = [
        ("maria@test.com", "+34 612 345 678", "phone_mobile", True),
        ("maria@test.com", "maria.garcia@work.com", "email_work", False),
        ("joan@test.com", "+34 623 456 789", "phone_mobile", True),
        ("carlos@test.com", "+34 634 567 890", "phone_mobile", True),
        ("laura@test.com", "+34 645 678 901", "phone_mobile", True),
        ("david@test.com", "+34 656 789 012", "phone_mobile", True),
    ]

    count = 0
    for email, value, type_code, is_primary in contact_data:
        person = db.query(Person).filter(Person.email == email).first()
        if not person:
            continue
        ct = db.query(ContactType).filter(ContactType.code == type_code).first()
        existing = db.query(Contact).filter(
            Contact.entity_type == "person",
            Contact.entity_id == person.id,
            Contact.value == value,
        ).first()
        if existing:
            continue
        db.add(Contact(
            entity_type="person",
            entity_id=person.id,
            contact_type_id=ct.id if ct else None,
            value=value,
            is_primary=is_primary,
        ))
        count += 1

    # Add bank IBANs, payment method, holder name for a few members
    iban_data = [
        ("maria@test.com", "ES6621000418401234567891", "CAIXESBBXXX", "María García"),
        ("joan@test.com", "ES7920385778983000760236", "CAIXESBBXXX", "Joan Puig"),
        ("carlos@test.com", "ES9121000418450200051332", "CAIXESBBXXX", "Carlos López"),
    ]
    for email, iban, bic, holder in iban_data:
        person = db.query(Person).filter(Person.email == email).first()
        if person and not person.bank_iban:
            person.bank_iban = iban
            person.bank_bic = bic
            person.bank_holder_name = holder
            person.payment_method = "direct_debit"

    # Set gender for test members
    gender_data = [
        ("maria@test.com", "female"),
        ("joan@test.com", "male"),
        ("carlos@test.com", "male"),
        ("laura@test.com", "female"),
        ("anna@test.com", "female"),
        ("marta@test.com", "female"),
        ("jordi@test.com", "male"),
        ("elena@test.com", "female"),
        ("alex@test.com", "non_binary"),
    ]
    for email, gender in gender_data:
        person = db.query(Person).filter(Person.email == email).first()
        if person and not person.gender:
            person.gender = gender

    db.flush()
    print(f"  Member contacts: {count} contacts + {len(iban_data)} bank details + {len(gender_data)} genders")


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

    # Find test member (member@test.com) — limit to 3 registrations so some activities remain unregistered for testing
    test_member_user = db.query(User).filter(User.email == "member@test.com").first()
    test_member = db.query(Member).filter(Member.user_id == test_member_user.id).first() if test_member_user else None
    test_member_reg_count = 0
    test_member_max_regs = 3

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

        # Register a varying number of members per activity
        max_to_register = min(len(members), activity.max_participants, 10)
        members_to_register = members[:max_to_register]

        for i, member in enumerate(members_to_register):
            # Skip test member after they've reached their registration limit
            if test_member and member.id == test_member.id and test_member_reg_count >= test_member_max_regs:
                continue
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

            # Track test member registrations
            if test_member and member.id == test_member.id and status != "cancelled":
                test_member_reg_count += 1

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
    first_activity = True

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

        # Fixed amount code for the first activity (Summer Soccer Camp) only
        if first_activity:
            first_activity = False
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
            title="Exoneració de responsabilitat",
            content="Reconec que la participació en aquesta activitat comporta riscos inherents. "
                    "Accepto la plena responsabilitat de qualsevol lesió o dany que pugui ocórrer durant l'activitat. "
                    "Eximeixo l'organització i el seu personal de qualsevol responsabilitat.",
            is_mandatory=True,
            display_order=1,
            is_active=True,
        ))
        count += 1

        # Optional image rights consent
        db.add(ActivityConsent(
            activity_id=activity.id,
            title="Drets d'imatge",
            content="Consento l'ús de fotografies i vídeos presos durant aquesta activitat "
                    "amb finalitats promocionals al lloc web i xarxes socials de l'organització.",
            is_mandatory=False,
            display_order=2,
            is_active=True,
        ))
        count += 1

    # Add a GDPR-style mandatory consent to the first activity
    if activities:
        db.add(ActivityConsent(
            activity_id=activities[0].id,
            title="Consentiment de tractament de dades",
            content="Consento el tractament de les meves dades personals (nom, informació de contacte, "
                    "dades relacionades amb la salut si escau) amb la finalitat de gestionar la meva inscripció "
                    "i participació en aquesta activitat, d'acord amb el RGPD.",
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
            name="Certificat mèdic",
            description="Un certificat mèdic que confirmi l'aptitud per participar en activitats físiques. Ha d'haver estat emès en els últims 12 mesos.",
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
            name="Foto d'identitat",
            description="Una foto tipus carnet per a l'acreditació del participant.",
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
            name="Document d'assegurança",
            description="Justificant d'assegurança de responsabilitat civil o assegurança esportiva.",
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


def seed_billing_data(db) -> None:
    """Create sample concepts and receipts for billing testing."""
    from datetime import date, timedelta
    from decimal import Decimal

    existing = db.query(Concept).count()
    if existing > 0:
        print(f"  Billing: already seeded ({existing} concepts)")
        return

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    admin = db.query(User).filter(User.role == "admin").first()
    created_by = admin.id if admin else None

    # --- Concepts ---
    concepts = {
        "full": Concept(name="Quota Full Member — Anual", code="membership-full-member", concept_type="membership", default_amount=600.00, vat_rate=21.00),
        "student": Concept(name="Quota Student — Anual", code="membership-student", concept_type="membership", default_amount=300.00, vat_rate=21.00),
        "youth": Concept(name="Quota Youth — Anual", code="membership-youth", concept_type="membership", default_amount=180.00, vat_rate=10.00),
        "senior": Concept(name="Quota Senior — Anual", code="membership-senior", concept_type="membership", default_amount=360.00, vat_rate=21.00),
        "activity": Concept(name="Inscripció Activitat", code="activity-registration", concept_type="activity", default_amount=0, vat_rate=21.00),
        "manual": Concept(name="Altres Conceptes", code="manual-other", concept_type="manual", default_amount=0, vat_rate=21.00),
    }
    for c in concepts.values():
        db.add(c)
    db.flush()
    print(f"  Concepts: created {len(concepts)}")

    # --- Receipts ---
    today = date.today()
    year = today.year
    prefix = org.invoice_prefix or "FAC"
    period_start = date(year, 1, 1)
    period_end = date(year, 12, 31)
    seq = 1

    def next_number():
        nonlocal seq
        num = f"{prefix}-{year}-{seq:04d}"
        seq += 1
        return num

    # Get members with their types for realistic data
    members_data = (
        db.query(Member, MembershipType, Person)
        .join(MembershipType, Member.membership_type_id == MembershipType.id)
        .join(Person, Member.person_id == Person.id)
        .filter(Member.is_active.is_(True))
        .limit(20)
        .all()
    )

    receipt_count = 0

    # Map membership type slugs to concept keys
    slug_to_concept = {
        "full-member": "full",
        "student": "student",
        "youth": "youth",
        "senior": "senior",
    }

    for member, mtype, person in members_data:
        concept_key = slug_to_concept.get(mtype.slug)
        if not concept_key or concept_key not in concepts:
            concept_key = "full"
        concept = concepts[concept_key]
        base = Decimal(str(concept.default_amount))
        if base <= 0:
            base = Decimal(str(mtype.base_price)) if mtype.base_price else Decimal("50")
        vat_rate = Decimal(str(concept.vat_rate))
        vat = (base * vat_rate / Decimal("100")).quantize(Decimal("0.01"))
        total = base + vat

        desc = f"{mtype.name} — {person.first_name} {person.last_name}"

        # Determine status: distribute across statuses for realistic data
        idx = receipt_count % 12
        if idx < 5:
            status, pay_method, pay_date = "paid", "direct_debit", today - timedelta(days=30)
        elif idx < 7:
            status, pay_method, pay_date = "emitted", None, None
        elif idx == 7:
            status, pay_method, pay_date = "overdue", None, None
        elif idx == 8:
            status, pay_method, pay_date = "returned", None, None
        elif idx == 9:
            status, pay_method, pay_date = "cancelled", None, None
        elif idx == 10:
            status, pay_method, pay_date = "new", None, None
        else:
            status, pay_method, pay_date = "pending", None, None

        receipt = Receipt(
            receipt_number=next_number(),
            member_id=member.id,
            concept_id=concept.id,
            origin="membership",
            description=desc,
            base_amount=base,
            vat_rate=vat_rate,
            vat_amount=vat,
            total_amount=total,
            status=status,
            payment_method=pay_method,
            emission_date=today - timedelta(days=60),
            due_date=today - timedelta(days=30),
            payment_date=pay_date,
            return_date=(today - timedelta(days=15)) if status == "returned" else None,
            return_reason="Fondos insuficientes" if status == "returned" else None,
            billing_period_start=period_start,
            billing_period_end=period_end,
            is_batchable=True,
            created_by=created_by,
        )
        db.add(receipt)
        receipt_count += 1

    # Activity receipts — from registrations with amounts
    registrations = (
        db.query(Registration)
        .filter(Registration.discounted_amount > 0, Registration.status == "confirmed")
        .limit(5)
        .all()
    )
    activity_concept = concepts["activity"]
    for reg in registrations:
        activity = db.query(Activity).filter(Activity.id == reg.activity_id).first()
        base = Decimal(str(reg.discounted_amount))
        vat_rate = Decimal("21")
        vat = (base * vat_rate / Decimal("100")).quantize(Decimal("0.01"))
        total = base + vat

        receipt = Receipt(
            receipt_number=next_number(),
            member_id=reg.member_id,
            concept_id=activity_concept.id,
            registration_id=reg.id,
            origin="activity",
            description=activity.name if activity else "Activity",
            base_amount=base,
            vat_rate=vat_rate,
            vat_amount=vat,
            total_amount=total,
            status="paid",
            payment_method="card",
            emission_date=today - timedelta(days=20),
            payment_date=today - timedelta(days=20),
            is_batchable=True,
            created_by=created_by,
        )
        db.add(receipt)
        receipt_count += 1

    # Manual receipts
    manual_concept = concepts["manual"]
    manual_items = [
        ("Lloguer sala — Març 2026", Decimal("200"), "paid", "cash"),
        ("Material esportiu", Decimal("85.50"), "paid", "bank_transfer"),
        ("Quota extraordinària assemblea", Decimal("30"), "emitted", None),
    ]
    # Pick a random member for manual receipts
    if members_data:
        manual_member = members_data[0][0]
        for desc, base, status, pay_method in manual_items:
            vat_rate = Decimal("21")
            vat = (base * vat_rate / Decimal("100")).quantize(Decimal("0.01"))
            total = base + vat
            receipt = Receipt(
                receipt_number=next_number(),
                member_id=manual_member.id,
                concept_id=manual_concept.id,
                origin="manual",
                description=desc,
                base_amount=base,
                vat_rate=vat_rate,
                vat_amount=vat,
                total_amount=total,
                status=status,
                payment_method=pay_method,
                emission_date=today - timedelta(days=10),
                due_date=today + timedelta(days=20),
                payment_date=(today - timedelta(days=5)) if status == "paid" else None,
                is_batchable=pay_method != "cash",
                created_by=created_by,
            )
            db.add(receipt)
            receipt_count += 1

    # Ensure member@test.com has an emitted receipt for Stripe Checkout testing
    test_member_user = db.query(User).filter_by(email="member@test.com").first()
    if test_member_user:
        test_member = (
            db.query(Member)
            .filter(Member.person_id == test_member_user.person_id)
            .first()
        )
        if test_member:
            has_emitted = (
                db.query(Receipt)
                .filter(
                    Receipt.member_id == test_member.id,
                    Receipt.status == "emitted",
                )
                .count()
            )
            if not has_emitted:
                concept = concepts.get("full") or concepts.get("manual")
                base = Decimal("50.00")
                vat_rate = Decimal("21")
                vat = Decimal("10.50")
                total = Decimal("60.50")
                receipt = Receipt(
                    receipt_number=next_number(),
                    member_id=test_member.id,
                    concept_id=concept.id if concept else None,
                    origin="membership",
                    description=f"Annual membership — {test_member_user.person.first_name} {test_member_user.person.last_name}",
                    base_amount=base,
                    vat_rate=vat_rate,
                    vat_amount=vat,
                    total_amount=total,
                    status="emitted",
                    emission_date=today - timedelta(days=5),
                    due_date=today + timedelta(days=25),
                    is_batchable=False,
                    created_by=created_by,
                )
                db.add(receipt)
                receipt_count += 1

    db.flush()
    print(f"  Receipts: created {receipt_count} ({receipt_count - len(manual_items) - len(registrations)} membership, {len(registrations)} activity, {len(manual_items)} manual)")


def seed_sepa_data(db) -> None:
    """Create SEPA mandates, a payment provider, and a sample remittance for testing."""
    from datetime import date, timedelta
    from decimal import Decimal

    existing = db.query(SepaMandate).count()
    if existing > 0:
        print(f"  SEPA: already seeded ({existing} mandates)")
        return

    # --- Set creditor_id on org settings ---
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if org and not org.creditor_id:
        org.creditor_id = "ES12000B12345678"
        org.sepa_format = "pain.008"
        db.flush()
        print("  Org creditor_id: set to ES12000B12345678")

    # --- Payment provider ---
    provider = PaymentProvider(
        provider_type="sepa_direct_debit",
        display_name="SEPA Direct Debit",
        status="active",
        config={"format": "pain.008.001.02"},
        is_default=True,
    )
    db.add(provider)
    db.flush()
    print("  Payment provider: created SEPA Direct Debit")

    # --- Disabled provider templates for other types ---
    provider_templates = [
        PaymentProvider(
            provider_type="stripe",
            display_name="Stripe",
            status="disabled",
            config={"secret_key": "", "publishable_key": "", "webhook_secret": "", "mode": "webhook"},
            is_default=False,
        ),
        PaymentProvider(
            provider_type="redsys",
            display_name="Redsys",
            status="disabled",
            config={"merchant_code": "", "terminal_id": "", "secret_key": "", "environment": "test", "currency_code": "978"},
            is_default=False,
        ),
        PaymentProvider(
            provider_type="goCardless",
            display_name="GoCardless",
            status="disabled",
            config={"access_token": "", "webhook_secret": "", "environment": "sandbox"},
            is_default=False,
        ),
        PaymentProvider(
            provider_type="paypal",
            display_name="PayPal",
            status="disabled",
            config={"client_id": "", "client_secret": "", "environment": "sandbox"},
            is_default=False,
        ),
    ]
    for tmpl in provider_templates:
        db.add(tmpl)
    db.flush()
    print("  Payment providers: created Stripe, Redsys, GoCardless, PayPal (disabled)")

    # --- Add bank IBANs to more members (for mandate variety) ---
    extra_iban_data = [
        ("anna@test.com", "ES8023100001180000012345", "CAIXESBBXXX", "Anna Ferrer"),
        ("marta@test.com", "ES6000491500051234567892", "BSCHESMMXXX", "Marta Soler"),
        ("jordi@test.com", "ES2100820532161234567890", "BSABESBBXXX", "Jordi Vidal"),
        ("elena@test.com", "ES7100302053091234567895", "BARKESMMXXX", "Elena Ruiz"),
        ("alex@test.com", "ES3801822200160201234567", "BBVAESMMXXX", "Àlex Serra"),
    ]
    for email, iban, bic, holder in extra_iban_data:
        person = db.query(Person).filter(Person.email == email).first()
        if person and not person.bank_iban:
            person.bank_iban = iban
            person.bank_bic = bic
            person.bank_holder_name = holder
            person.payment_method = "direct_debit"
    db.flush()

    # --- Create mandates ---
    # Members who already have IBANs: maria, joan, carlos (from seed_member_contacts)
    # + anna, marta, jordi, elena, alex (added above)
    mandate_members = [
        # (email, status) — 6 active, 1 cancelled, 1 without mandate (for testing exclusion)
        ("maria@test.com", "active"),
        ("joan@test.com", "active"),
        ("carlos@test.com", "active"),
        ("anna@test.com", "active"),
        ("marta@test.com", "active"),
        ("jordi@test.com", "cancelled"),
        ("elena@test.com", "active"),
        # alex@test.com intentionally left without a mandate (for exclusion testing)
    ]

    today = date.today()
    mandate_count = 0
    for email, mandate_status in mandate_members:
        person = db.query(Person).filter(Person.email == email).first()
        if not person or not person.bank_iban:
            continue
        member = db.query(Member).join(Person, Member.person_id == Person.id).filter(Person.email == email).first()
        if not member:
            continue

        seq = mandate_count + 1
        reference = f"FAC-{member.member_number}-{seq:03d}"
        signed_date = today - timedelta(days=90 + mandate_count * 5)

        mandate = SepaMandate(
            member_id=member.id,
            mandate_reference=reference,
            creditor_id=org.creditor_id,
            debtor_name=f"{person.first_name} {person.last_name}",
            debtor_iban=person.bank_iban,
            debtor_bic=person.bank_bic,
            mandate_type="recurrent",
            signature_method="paper",
            status=mandate_status,
            signed_at=signed_date,
            cancelled_at=today - timedelta(days=10) if mandate_status == "cancelled" else None,
        )
        db.add(mandate)
        mandate_count += 1

    db.flush()
    print(f"  SEPA mandates: created {mandate_count} (6 active, 1 cancelled)")

    # --- Ensure some receipts are emitted + batchable for remittance testing ---
    # Update a few receipts to be emitted/batchable for members with active mandates
    active_mandate_member_ids = [
        m.member_id
        for m in db.query(SepaMandate).filter(SepaMandate.status == "active").all()
    ]
    batchable_receipts = (
        db.query(Receipt)
        .filter(
            Receipt.member_id.in_(active_mandate_member_ids),
            Receipt.status.in_(["emitted", "overdue"]),
            Receipt.is_batchable.is_(True),
            Receipt.remittance_id.is_(None),
        )
        .limit(6)
        .all()
    )
    if len(batchable_receipts) >= 4:
        print(f"  Batchable receipts: {len(batchable_receipts)} receipts ready for remittance testing")
    else:
        # Create extra batchable receipts to ensure enough for testing
        concept = db.query(Concept).filter(Concept.concept_type == "membership").first()
        if concept and active_mandate_member_ids:
            receipt_prefix = org.invoice_prefix or "FAC"
            year = today.year
            # Find next receipt number
            last_receipt = db.query(Receipt).order_by(Receipt.id.desc()).first()
            seq_start = 100  # high number to avoid collisions
            if last_receipt:
                try:
                    parts = last_receipt.receipt_number.split("-")
                    seq_start = int(parts[-1]) + 1
                except (ValueError, IndexError):
                    pass

            for i, member_id in enumerate(active_mandate_member_ids[:4]):
                member = db.query(Member).filter(Member.id == member_id).first()
                person = db.query(Person).filter(Person.id == member.person_id).first() if member else None
                if not member or not person:
                    continue
                base = Decimal("50.00")
                vat = Decimal("10.50")
                total = Decimal("60.50")
                receipt = Receipt(
                    receipt_number=f"{receipt_prefix}-{year}-{seq_start + i:04d}",
                    member_id=member_id,
                    concept_id=concept.id,
                    origin="membership",
                    description=f"SEPA test — {person.first_name} {person.last_name}",
                    base_amount=base,
                    vat_rate=Decimal("21"),
                    vat_amount=vat,
                    total_amount=total,
                    status="emitted",
                    emission_date=today - timedelta(days=15),
                    due_date=today + timedelta(days=15),
                    is_batchable=True,
                )
                db.add(receipt)
            db.flush()
            print(f"  SEPA test receipts: created {min(4, len(active_mandate_member_ids))} emitted batchable receipts")

    print("  SEPA seed: complete — ready for manual SEPA workflow testing")


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

            print("\nSeeding member contacts...")
            seed_member_contacts(db)

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

            print("\nSeeding billing data...")
            seed_billing_data(db)

            print("\nSeeding SEPA data...")
            seed_sepa_data(db)

            print("\n  ⚠  TEST ACCOUNTS — do NOT use in production:")
            for account in TEST_ACCOUNTS:
                print(f"     {account['role']:15s} {account['email']:25s} / {account['password']}")
            print(f"     {'member':15s} {'(+22 extra members)':25s} / TestMember1!")
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
