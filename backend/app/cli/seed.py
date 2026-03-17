"""CLI seed command — populates initial data for a fresh Memship installation.

Creates:
- Organization settings (defaults)
- Address types (home, work, billing, legal, venue)
- Contact types (phone_home, phone_mobile, phone_work, phone_emergency, email_work, email_other)
- Default membership type
- First super admin account (interactive prompts)
- First org admin account (interactive prompts)

Usage:
    python -m app.cli.seed
"""

import getpass
import sys

from argon2 import PasswordHasher
from sqlalchemy import text

from app.db.session import SessionLocal
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import AddressType, ContactType, Person
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType

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


def seed_default_membership_type(db) -> MembershipType:
    existing = db.query(MembershipType).filter_by(slug="general").first()
    if existing:
        print(f"  Default membership type: already exists ({existing.name})")
        return existing

    mt = MembershipType(
        name="General",
        slug="general",
        description="Default membership type",
        base_price=0,
        billing_frequency="annual",
        is_active=True,
    )
    db.add(mt)
    db.flush()
    print("  Default membership type: created 'General'")
    return mt


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


def main() -> None:
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

        print("\nSeeding membership types...")
        membership_type = seed_default_membership_type(db)

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
