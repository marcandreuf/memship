🌐 **English** | [Español](README.es.md) | [Català](README.ca.md)

# Memship

> **This project is under active development and open to any feedback via gihub [issues or feature requests](https://github.com/marcandreuf/memship/issues).**

**Membership management for everyone.**

Memship is a self-hosted, open-source membership management system designed for professional associations, sports clubs, cultural organizations, and any member-based entity. Deploy it on your own infrastructure, own your data, and manage your community with modern tooling.

---

## What we're building

Most membership tools are either expensive SaaS platforms or outdated legacy software. Memship aims to change that — a modern, full-featured solution that you control. No vendor lock-in, no per-member pricing, no data leaving your servers.

- **Self-hosted** — runs on any server with Docker
- **Single-tenant** — one database per organization, complete data isolation
- **Multi-language** — Spanish, Catalan, and English from day one. Extensible to any language via community contributions
- **GDPR-ready** — built-in legal terms templates and consent management

## Quick Start (Docker)

> **For trying memship out, not for running it.** This is the fastest path to a
> working instance on your own machine: published images, throwaway volumes, and
> a fixed database password. To run memship for a real organization, follow
> [Installation](docs/getting-started/installation.md) instead — same product,
> set up so it can be backed up, upgraded and kept.

Try memship with a single command — no cloning required:

```bash
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml
docker compose pull        # fetch the latest published images
PORT=8081 docker compose up -d
```

Then run the setup, which walks you through three questions:

```bash
docker compose exec -it demo-memship-api python -m app.cli.seed
```

1. **Super admin** — you choose the address and password. Nothing is preset.
2. **Club data** — offered only if there is any, so it is a no-op on a fresh install.
3. **Club setup** — enter your organization's real details, or generate a demo club.

Choose the demo club to look around: it creates a full year of realistic sample
data — ~60 members across all statuses, activities, receipts in every state
spread across the months, SEPA mandates and dashboard reminders. It also
generates logins for a club admin and two members and **prints those passwords
once**, so keep the output. Safe to re-run (idempotent).

Open http://localhost:8081 and log in as your super admin. Change `PORT=8081` to
any port you prefer (default is 80).

Once you are done evaluating, re-run the same command and answer *yes* to the
club-data question: it clears the demo club while keeping your super admin and
any payment providers you configured. See
[First-time setup](docs/getting-started/first-setup.md).

## Releases

Memship follows [semantic versioning](https://semver.org/), and **version numbers are assigned at release time — never reserved in advance.** One line per version below; the full notes for each are on the [releases page](https://github.com/marcandreuf/memship/releases). What is coming next is under [Roadmap](#roadmap), and [Choosing a version](CONTRIBUTING.md#choosing-a-version) covers how a number is picked.

| Version | Milestone | Status |
|---------|-----------|--------|
| v0.1.0 | Member Management MVP — auth, RBAC, member CRUD, membership types, i18n, Docker, CI | Done |
| v0.1.1 | Email sending (SMTP) — welcome emails, password reset emails | Done |
| v0.1.2 | Groups, guardian/minor support, restricted role (schema) | Done |
| v0.1.3 | Caddy reverse proxy, backup/restore scripts, self-hosted polish | Done |
| v0.1.4 | Organization settings management (API + frontend) | Done |
| v0.1.5 | Activity CRUD — models, modalities, pricing, admin frontend | Done |
| v0.1.6 | Strong entity pattern — unified list/detail/tabs across all entities | Done |
| v0.2.0 | Activity Management — registration, eligibility, waitlist, discounts, consents, attachments | Done |
| v0.2.1 | UX refactor — Shadcn sidebar, dark mode, brand colors, compact tables, quick start | Done |
| v0.2.2 | E2E test foundation (Cypress) — auth, members, activities, registrations | Done |
| v0.2.3 | Error handling & validation hardening — toast notifications, global error handler, backend schema validation, StrEnum, 76 validation tests, 16 E2E tests | Done |
| v0.2.4 | Bug fixes — dark mode sidebar, form error display, route guards, member list cancelled visibility, member delete removed | Done |
| v0.2.5 | Activity UX — member activity card redesign, cover image upload, registration status badges, activity list thumbnails, My Activities grid, Docker storage volume | Done |
| v0.2.6 | Bug fixes & testing — Shadcn confirm dialogs (replaced 13 browser alerts), seed discount code fix, self-cancellation deadline check, re-registration after cancel, 21 new API tests, 9 new E2E eligibility tests | Done |
| v0.2.7 | Activity polish — loading skeletons, nuqs URL state | Done |
| v0.2.9 | Payment prerequisites — org address & banking, logo upload, contact info tab, member IBAN, Celery/Redis, email notifications (Jinja2 + SMTP/Resend) | Done |
| v0.3.0 | Basic Payments & Invoicing — receipts, PDF generation, VAT, fee generation, member payment history | Done |
| v0.3.1 | Bug fixes — failing tests and translated readme files | Done |
| v0.3.2 | Bug fixes — frontend build pipeline fix | Done |
| v0.3.3 | CI improvements — faster test execution | Done |
| v0.3.4 | Bug fixes — warning cleanup and integration test optimizations | Done |
| v0.3.5 | Bug fixes — failing integration tests | Done |
| v0.3.6 | CI optimization — setup-uv v7, cached password hashing, pytest-xdist parallel workers, automated version hooks | Done |
| v0.4.0 | SEPA Direct Debit — mandate management, remittance batches, pain.008 XML, member payment method | Done |
| v0.4.1 | Payment provider settings — super admin configurable payment gateway management | Done |
| v0.4.2 | Webhook infrastructure + Stripe Checkout — provider webhooks, real-time payment status, member "Pay Now" flow | Done |
| v0.4.3 | Redsys integration — Spanish bank gateway with 3D Secure + Bizum | Done |
| v0.4.4 | Recurring billing — scheduled fee generation | Done |
| v0.4.5 | Payment reminders — overdue email notifications | Done |
| v0.5.0 | Simple Communications — admin announcements to all/group/membership type | Done |
| v0.5.1 | Communications sent view — recipient tracking + in-app "Seen" | Done |
| v0.7.0 | Digital Member Card + QR Check-in — PDF card, auto member numbers | Done |
| v0.7.1 | Member card polish — admin card view on member page, member profile photo upload, profile page redesign | Done |
| v1.0.0 | Stabilization & Release — CSV exports, finance dashboard, notes & reminders, annual summary, demo seed, docs polish | Done |
| v1.0.1 | Patch — fix Celery scheduled billing/reminder task registration; CI guard against image tag overwrite | Done |
| v1.1.0 | Custom profile fields — org-configurable member data (text, number, date, select, …) with per-field validation and per-field visibility/editability | Done |
| v1.1.1 | Patch — settings navigation reorganised: payment and member settings grouped under Payments and Members tabs | Done |
| v1.2.2 | SSO and mailing configuration — public registration with email verification and an admin approval flow, Google / Apple sign-in, and Resend / Google SMTP setup from an Integrations tab | Done |
| v1.3.0 | Simple Bookings — member reservations of shared spaces on a week calendar, with per-slot capacity and a FIFO waitlist | Done |
| v1.4.0 | Flexible roles & permissions — multi-role assignment and granular per-permission checks in place of the four fixed roles. Also repairs deployment stacks that ran no Celery worker and mounted no volume on the API service | Done |
| v2.0.0 | Self-hosting overhaul — host-visible bind mounts under one `MEMSHIP_DATA_ROOT`, backend containers running as the operator's uid, and a one-command `install.sh`. **Security:** PostgreSQL and the API are no longer published to the internet. **Breaking:** `uv run` no longer works in the containers, and existing installs need a one-off `chown` | Done |
| v2.1.0 | Setup without published credentials — the same interactive setup on every environment, with no accounts whose passwords ship in this repository, plus unattended flags for scripted installs | Done |
| v2.2.0 | Super admin recovery from the host — a super admin's password is reset with `python -m app.cli.seed` on the server rather than by email. **Security:** mailbox access was equivalent to owning the instance | Done |
| v2.3.0 | Uploaded files behind authentication, and sign-in that cannot be guessed at forever — **Security:** the storage directory was served by a static-file mount, reset tokens came back in API responses, and the published placeholder signing key was the Compose default. **Breaking:** installs on that placeholder key get a fresh one, signing everyone out | Done |
| v2.3.1 | Money paths that were wrong quietly — a SEPA file no longer drops receipts whose mandate was cancelled, a payment webhook no longer records a mismatched amount as paid in full, and an activity can no longer be over-booked by two people registering at once. **Behaviour:** a remittance whose mandate vanished now fails with an error instead of producing a short file, and a payment for the wrong amount leaves the receipt unpaid for review | Done |
| v2.4.0 | Sign-in requires a confirmed email address, and invoice numbers are sequential and unbroken. **Breaking:** an account that never confirmed its address can no longer sign in — `python -m app.cli.verify_email` confirms one from the host when the confirmation email is what is broken. **Migration:** receipt numbering moves to a counter per year, seeded from the numbers already issued | Done |
| v2.5.0 | Every outbound email in one branded layout — the organisation's name, logo and colour come from the settings row, every message now carries a plain-text alternative alongside the HTML, and receipt delivery and the recurring-billing summary are templates rather than inline markup. Also: a registration whose receipt fails to generate is no longer rolled back with it, and `SEED_EMAIL_DOMAIN` lets an install that deliberately sends real mail seed a demo club at a domain that can receive it | Done |
| v2.6.0 | A super admin chooses which emails the system sends — a Settings screen with a switch per template, and all 17 senders routed through one gate instead of mailing unconditionally. The announcements feature flag now closes its endpoints rather than only hiding the navigation, and an unreadable template policy fails closed, because it is not consent. **Breaking:** optional email now defaults to off, so an existing installation goes quiet on upgrade until a super admin enables the templates it wants — only address verification and password reset keep sending | Done |
| v2.7.0 | Sessions that slide rather than expiring mid-task — an active session renews itself halfway through its window, and when it does run out it says so and returns you to sign-in instead of failing a request silently. Spaces and the billing lists move onto the same list and detail chrome the rest of the app already uses, and the last English-only screens are translated. **Self-hosting:** a release deploys to a VPS that holds no git and no source checkout; the install and upgrade guides fetch a release tarball instead of cloning; and a first install now names the file holding the keys a lost host would take with it, with `scripts/pull-backup.sh` to copy them off | Done |

## Roadmap

Priority-ordered, not yet versioned. Each becomes a versioned release when it ships, and the release claims the next semver number in order. Each item has an issue carrying its summary and current thinking — see the [`roadmap` issues](https://github.com/marcandreuf/memship/labels/roadmap).

- **User invitations** — invite a new super admin, club admin or member by email address and role; they set their own name and password. Sent by email where email is configured, and as a copyable link where it is not, so a freshly installed instance can add a second administrator without shell access
- **Data backups** — download a full backup from the admin area, covering the database and the uploaded files, with a documented and tested restore
- **Convocations** — formal General Assembly calls with token-based member RSVP
- **Document library** — statutes, minutes, forms with per-group visibility
- **Events calendar + RSVP** — calendar view and participation tracking
- **Integrations** — connect memship to the tools a club already runs on, instead of asking it to move. Instant messaging first (WhatsApp, Telegram, Signal, Instagram), since that is where most clubs actually communicate; then calendar subscriptions, accounting and e-invoicing exports, sports-federation licence submissions, and outbound webhooks as the generic escape hatch. Each connector has its own cost and constraints and ships on its own

Complex variations are built on demand, when a real deployment needs them: GoCardless e-mandates, PayPal, Stripe Invoice flow, bulk receipt actions, custom report builder, surveys, family group billing, paid & recurring bookings, equipment rental, convocation voting & document attachments, and similar deeper cuts of the features above.

**Deferred — extensions as a modules/plugins system.** Optional add-ons such as photo albums, a forum, a guestbook, a weblinks directory, inventory/lending and portal widgets need a module system designed into the architecture rather than added on top of it. This waits for a future revision of that architecture instead of shipping as a feature.

---

## Features

**Member Management** (available now)
- Full member lifecycle: registration, onboarding, status changes, cancellation
- Membership types with groups, pricing, and age restrictions
- Guardian/minor support
- Role-based access: super admin, org admin, member
- Organization settings with branding (color, logo upload), address, banking (IBAN/BIC), invoice series
- Member contact info management (phone, email, with contact types)
- Member bank details (IBAN/BIC) for SEPA direct debit
- Multi-language interface (ES, CA, EN) with locale selector in profile
- Admin dashboard with status charts (recharts)
- Unified entity pattern: list → detail → tabs for all entities
- Email notifications (registration confirmation, cancellation, waitlist promotion) via Celery/Redis
- Dual email transport: SMTP (self-hosted) or Resend API (managed)
- Jinja2 email templates with locale support (ES/CA/EN)

**Activities & Events** (available now)
- Activity creation with lifecycle management (draft → published → archived)
- Cover image upload per activity (admin upload, member-visible thumbnails)
- Modalities (variants with independent capacity, pricing, and deadlines)
- Pricing tiers with time-based validity (early bird pricing)
- Online registration with eligibility checks (membership type, age, status)
- Capacity management with automatic waiting list and promotion
- Self-cancellation with configurable deadlines
- Discount codes (percentage/fixed, max uses, validity dates)
- Per-activity legal consents (mandatory/optional)
- Per-activity required attachments with file upload
- Member portal: activity browsing with thumbnails, registration status badges, "My Activities" grid
- Admin portal: registration management with status changes

**Payments & Invoicing** (available now)
- Receipt management with 7-status lifecycle (new → emitted → paid / returned / cancelled / overdue)
- PDF receipt generation (WeasyPrint) with org header, member details, VAT breakdown — 3 locales (ES/CA/EN)
- Bulk membership fee generation from membership types
- Auto-receipt on activity registration (emitted on confirmation, cancelled on cancellation)
- Manual receipt creation from member detail page
- VAT/IVA calculation with configurable default rate per organization
- Invoice numbering with configurable prefix and optional annual reset (e.g., FAC-2026-0001)
- European currency formatting (1.234,56 €) based on org locale
- Member self-service: "My Receipts" page with PDF download
- Admin dashboard: receipt status chart + pending/paid/overdue amount cards
- Receipt email notification with PDF attachment (via Celery + Resend or SMTP)
- Settings → Payments tab for invoicing and banking configuration

**SEPA Direct Debit** (available — v0.4.0)
- SEPA mandate management (create, PDF, upload signed, cancel)
- Remittance batch processing with SEPA XML (pain.008.001.02)
- Bank return file import and receipt status tracking
- Member self-service payment method page

**Payment Providers** (in progress — v0.4.x)
- Configurable payment gateway management (super admin settings)
- Stripe Checkout — member self-service "Pay Now" for pending receipts
- Redsys SIS (TPV Virtual) — Spanish bank gateway with hosted 3D Secure V2 and Bizum (v0.4.3)
- Webhook infrastructure for real-time payment status updates (POST /webhooks/{provider})
- Extensible adapter pattern for regional providers (GoCardless, MercadoPago, Razorpay, etc.)

**Bookings & Spaces** (available now)
- Bookable spaces with daily opening hours and admin-defined dated slots
- Repeat rules that materialize a dated series (selected weekdays, every N weeks), plus whole-day slots
- Per-slot capacity with a FIFO waitlist and automatic promotion on cancellation
- Member week calendar with live occupancy, self-cancellation up to a configurable deadline
- Confirmation, waitlist, promotion and admin-cancellation emails

**Communications** (planned)
- Email campaigns with templates and audience targeting
- Direct messaging between admins and members
- Multi-language email templates

**Reports & Dashboards** (planned)
- Membership statistics and trends
- Financial summaries
- Data exports (CSV, PDF)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy / Alembic |
| Frontend | Next.js / React / Tailwind CSS / Shadcn/ui |
| Database | PostgreSQL 15 |
| Containers | Docker + Docker Compose |
| CI | GitHub Actions |
| Registry | GitHub Container Registry (ghcr.io) |

## Development

Backend in Docker, frontend locally with pnpm hot reload — driven by `scripts/dev.sh`:

```bash
./scripts/dev.sh start all      # backend (Docker) + frontend (local)
./scripts/dev.sh status
./scripts/dev.sh test           # backend suite
```

Full setup, every command, service URLs, seeding and the test suites are in
**[Local development environment](docs/development/local-environment.md)**.

See [CONTRIBUTING](CONTRIBUTING.md) for branching, versioning and how a release is cut.

## Installation (Docker)

Production self-hosting lives in the docs, so there is one copy of it to keep correct:

- **[Installation](docs/getting-started/installation.md)** — `vps-bootstrap.sh` on a bare server,
  then `install.sh`, which generates real secrets, pins a version and puts your data under one
  backed-up directory
- **[First-time setup](docs/getting-started/first-setup.md)** — create the super admin and the
  organization
- **[Configuration reference](docs/self-hosting/configuration.md)** — every environment variable
- **[Backups & restore](docs/self-hosting/backups-and-restore.md)** — set this up before going live
- **[Upgrading](docs/self-hosting/upgrading.md)** — moving to a new release
- **[Troubleshooting](docs/self-hosting/troubleshooting.md)** — when something will not start

The [Quick Start](#quick-start-docker) above is for evaluation only: it ships a signing key that is
published in this repository and keeps data in throwaway volumes.


## Contributing

Memship is in its early stages. Code contributions will be welcome once the project foundation is in place — stay tuned.

In the meantime, feel free to [open an issue](https://github.com/marcandreuf/memship/issues) to share ideas, suggest features, or ask questions. All feedback is welcome.

## License

Memship is licensed under the [Elastic License 2.0 (ELv2)](LICENSE). You are free to use, modify, and self-host Memship. The license restricts offering it as a managed service to third parties.
