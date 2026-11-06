<!-- source: es/admin-guide/overview.md -->
<!-- source-hash: 5086916e23fd -->

# Introduction to the administrator guide

This guide is for the **staff who run the organisation** from Memship's administration panel:
member registrations, activities, payments, communications and settings.

> **In Spanish:** [Introducción a la guía del administrador](../../es/admin-guide/overview.md).
> **En català:** [Introducció a la guia de l'administrador](../../ca/admin-guide/overview.md).

> **Language.** The administrator and member guides are written in Spanish first
> (`docs/es/`), because the people who run a club and its members are mostly Spanish speakers.
> All of them have an English version (`docs/en/`); the Catalan translation (`docs/ca/`) is in
> progress, and until it exists the Spanish page is served.

## Roles

Memship ships three system roles:

| Role                   | What they can do                                                             |
|------------------------|------------------------------------------------------------------------------|
| **Superadmin**         | Platform-level administration, including configuring the payment gateways.  |
| **Organisation administrator** | Day-to-day management: members, activities, billing and communications. |
| **Member**             | Using the member portal: profile, activities, payments, member card and bookings. |

Most of this guide is about the **organisation administrator**. The superadmin can also create
**custom roles** with the permissions they choose; see
[Roles and permissions](../reference/roles-and-permissions.md).

## Signing in

Access is with **email and password**. If you have forgotten your password, use the recovery
link on the sign-in screen (this requires [email delivery](../self-hosting/email.md) to be
configured).

## Panel areas

The administration panel is organised around these areas:

- **Dashboard**, a summary with member status and receipt status charts, and pending, paid
  and overdue amounts.
- **[Members](members.md)**, the full life cycle (registration, status changes, cancellation),
  membership types, groups and support for minors with a guardian.
- **[Entities](entities.md)**, companies, foundations and public bodies the club deals with,
  with receipts in their name (donations) without needing to make them members.
- **[Activities](activities.md)**, creation and publication, registrations with eligibility
  checks, waiting list, discount codes, consents and attachments.
- **[Payments](payments.md)**, receipts, fee generation, VAT, invoicing, PDF generation and
  online payment (Stripe, Redsys/Bizum).
- **[Donations](donations.md)**: the three paths for receiving a donation, and what record
  each one leaves.
- **[SEPA](sepa.md)**, direct debit mandates, remittances (pain.008 XML) and import of
  returns.
- **[Communications](communications.md)**, announcements to all members, to a group or to a
  membership type.
- **[Digital member card](member-cards.md)**, PDF member card with member number and QR
  check-in.
- **[Custom fields](custom-fields.md)**, profile fields configurable by the organisation.
- **[Reports](reports.md)**, CSV exports, financial dashboard and annual summary.
- **[Settings](settings.md)**, branding (name, colour, logo), address, bank details, invoicing
  and automations.

> Space booking (**Simple Bookings**) is not yet part of a published release and will be
> documented when it is released.

## Initial setup

Before registering real members, complete the [first setup](../getting-started/first-setup.md):
organisation details, branding, bank details and invoicing, and check that email delivery works.

## Guide pages

Each area (Members, Activities, Payments, etc.) has its own page. The
[documentation index](../README.md) lists them all.
