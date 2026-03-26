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
        features={},
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

    # Add bank IBANs for a few members
    iban_data = [
        ("maria@test.com", "ES6621000418401234567891", "CAIXESBBXXX"),
        ("joan@test.com", "ES7920385778983000760236", "CAIXESBBXXX"),
        ("carlos@test.com", "ES9121000418450200051332", "CAIXESBBXXX"),
    ]
    for email, iban, bic in iban_data:
        person = db.query(Person).filter(Person.email == email).first()
        if person and not person.bank_iban:
            person.bank_iban = iban
            person.bank_bic = bic

    db.flush()
    print(f"  Member contacts: {count} contacts + {len(iban_data)} bank IBANs")


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
