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
> a secret key that is committed to this repository. To run memship for a real
> organization, follow [Installation](docs/getting-started/installation.md)
> instead — same product, set up so it can be backed up, upgraded and kept.

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

## Roadmap

Memship follows [semantic versioning](https://semver.org/), and **version numbers are assigned at release time — never reserved on the roadmap in advance.** Below, the **Released** table is the shipped history; **Planned** is a priority-ordered list of what's next. A planned item is given a version only when it ships — see [Choosing a version](CONTRIBUTING.md#choosing-a-version) for how the number is picked.

### Released

| Version | Milestone                                                                                                                                                                                                        | Status |
|---------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------|
| v0.1.0 | Member Management MVP — auth, RBAC, member CRUD, membership types, i18n, Docker, CI                                                                                                                              | Done   |
| v0.1.1 | Email sending (SMTP) — welcome emails, password reset emails                                                                                                                                                     | Done   |
| v0.1.2 | Groups, guardian/minor support, restricted role (schema)                                                                                                                                                         | Done   |
| v0.1.3 | Caddy reverse proxy, backup/restore scripts, self-hosted polish                                                                                                                                                  | Done   |
| v0.1.4 | Organization settings management (API + frontend)                                                                                                                                                                | Done   |
| v0.1.5 | Activity CRUD — models, modalities, pricing, admin frontend                                                                                                                                                      | Done   |
| v0.1.6 | Strong entity pattern — unified list/detail/tabs across all entities                                                                                                                                             | Done   |
| v0.2.0 | Activity Management — registration, eligibility, waitlist, discounts, consents, attachments                                                                                                                      | Done   |
| v0.2.1 | UX refactor — Shadcn sidebar, dark mode, brand colors, compact tables, quick start                                                                                                                               | Done   |
| v0.2.2 | E2E test foundation (Cypress) — auth, members, activities, registrations                                                                                                                                         | Done   |
| v0.2.3 | Error handling & validation hardening — toast notifications, global error handler, backend schema validation, StrEnum, 76 validation tests, 16 E2E tests                                                         | Done   |
| v0.2.4 | Bug fixes — dark mode sidebar, form error display, route guards, member list cancelled visibility, member delete removed                                                                                         | Done   |
| v0.2.5 | Activity UX — member activity card redesign, cover image upload, registration status badges, activity list thumbnails, My Activities grid, Docker storage volume                                                 | Done   |
| v0.2.6 | Bug fixes & testing — Shadcn confirm dialogs (replaced 13 browser alerts), seed discount code fix, self-cancellation deadline check, re-registration after cancel, 21 new API tests, 9 new E2E eligibility tests | Done   |
| v0.2.7 | Activity polish — loading skeletons, nuqs URL state                                                                                                                                                              | Done   |
| v0.2.9 | Payment prerequisites — org address & banking, logo upload, contact info tab, member IBAN, Celery/Redis, email notifications (Jinja2 + SMTP/Resend)                                                              | Done   |
| v0.3.0 | Basic Payments & Invoicing — receipts, PDF generation, VAT, fee generation, member payment history                                                                                                               | Done   |
| v0.3.1 | Bug fixes — failing tests and translated readme files                                                                                                                                                            | Done   |
| v0.3.2 | Bug fixes — frontend build pipeline fix                                                                                                                                                                          | Done   |
| v0.3.3 | CI improvements — faster test execution                                                                                                                                                                          | Done   |
| v0.3.4 | Bug fixes — warning cleanup and integration test optimizations                                                                                                                                                   | Done   |
| v0.3.5 | Bug fixes — failing integration tests                                                                                                                                                                            | Done   |
| v0.3.6 | CI optimization — setup-uv v7, cached password hashing, pytest-xdist parallel workers, automated version hooks                                                                                                   | Done   |
| v0.4.0 | SEPA Direct Debit — mandate management, remittance batches, pain.008 XML, member payment method                                                                                                                  | Done   |
| v0.4.1 | Payment provider settings — super admin configurable payment gateway management                                                                                                                                  | Done   |
| v0.4.2 | Webhook infrastructure + Stripe Checkout — provider webhooks, real-time payment status, member "Pay Now" flow                                                                                                    | Done   |
| v0.4.3 | Redsys integration — Spanish bank gateway with 3D Secure + Bizum                                                                                                                                                 | Done   |
| v0.4.4 | Recurring billing — scheduled fee generation                                                                                                                                                                     | Done   |
| v0.4.5 | Payment reminders — overdue email notifications                                                                                                                                                                  | Done   |
| v0.5.0 | Simple Communications — admin announcements to all/group/membership type                                                                                                                                         | Done   |
| v0.5.1 | Communications sent view — recipient tracking + in-app "Seen"                                                                                                                                                    | Done   |
| v0.7.0 | Digital Member Card + QR Check-in — PDF card, auto member numbers                                                                                                                                                | Done   |
| v0.7.1 | Member card polish — admin card view on member page, member profile photo upload, profile page redesign                                                                                                          | Done   |
| v1.0.0 | Stabilization & Release — CSV exports, finance dashboard, notes & reminders, annual summary, demo seed, docs polish                                                                                              | Done   |
| v1.0.1 | Patch — fix Celery scheduled billing/reminder task registration; CI guard against image tag overwrite                                                                                                            | Done   |
| v1.1.0 | Custom profile fields — org-configurable member data (text, number, date, select, …) with per-field validation and per-field visibility/editability                                                              | Done   |
| v1.1.1 | Patch — settings navigation reorganised: payment and member settings grouped under Payments and Members tabs                                                                                                     | Done   |
| v1.2.2 | SSO / identity integration and mailing configuration — public registration + email-verification onboarding, admin approval flow, Google / Apple sign-in, superadmin SSO provider configuration and Resend / Google SMTP setup from an Integrations tab. Also drops a duplicate mailing-config migration whose revision id collided with an existing one, which made `alembic upgrade head` fail on startup | Done   |
| v1.3.0 | Simple Bookings — member reservations of shared spaces on a week calendar, per-slot capacity, FIFO waitlist with auto-promotion, and confirmation/waitlist emails | Done   |
| v1.4.0 | Flexible roles & permissions — multi-role assignment and granular per-permission checks in place of the four fixed roles, with a `/roles` management API and permission-driven navigation and page access across the portal. Also repairs the shipped deployment stacks, which ran no Celery worker — so every email the product sends was dropped silently, and the nightly billing and payment-reminder jobs never ran at all — and mounted no volume on the API service, so an upgrade destroyed uploaded files and regenerated the secret key that encrypts stored SSO and payment-provider credentials | Done   |
| v2.0.0 | Self-hosting overhaul — persistent data on host-visible bind mounts under a single `MEMSHIP_DATA_ROOT`, backend containers running as the operator's own uid, a one-command `install.sh`, and `vps-bootstrap.sh` for host preparation. **Security:** PostgreSQL and the API are no longer published to the internet — Docker writes its iptables rules ahead of the firewall's, so both were reachable on any host with a public IP in every earlier release. **Breaking:** `uv run` no longer works inside the containers, and existing installs need a one-off `sudo chown -R $(id -u):$(id -g) <data-root>/storage` | Done   |
| v2.1.0 | Setup without published credentials — initial setup is now the same interactive flow on every environment: you choose the super admin's address and password, and the fixed `super@examplee6e3b1.com` / `admin@examplee6e3b1.com` accounts are gone from the quickstart, where they were a super admin whose password ships in this repository. Adds unattended `--admin-email` and `--club-name` flags for scripted installs, a club-data reset that clears the club while keeping the super admin and any configured payment providers, and a demo-club generator that prints its logins once. Releases are safer too: every service is now built on every commit on `main`, and a release refuses to run when the validated release-candidate image is missing rather than quietly rebuilding from the tag | Done   |
| v2.2.0 | Super admin recovery from the host — the browser's forgot-password flow no longer accepts super admins, and their password is reset with `python -m app.cli.seed` on the machine running the containers. **Security:** that account holds the roles and credential permissions, so letting an email inbox reset it made mailbox access equivalent to owning the instance; the flow also silently dropped the mail on any install without SMTP, which is every install on day one. Password resets from the host are now written to the audit log, and the unattended `--admin-email` flag refuses an address belonging to an account that is not a super admin instead of resetting a stranger's password and reporting a super admin reset. Documents the recovery path and how to promote a second super admin, and fixes the install guide's first two commands, which could not work as written | Done   |
| v2.3.0 | Uploaded files behind authentication, and sign-in that cannot be guessed at forever — **Security:** uploaded files were served by a static-file mount over the whole storage directory, so the encryption key, generated SEPA files and scanned mandates were readable by anyone who guessed a path; they are now served by an authenticated route that checks ownership per folder. Password-reset and verification tokens were returned in the API response, so anyone could request a reset for someone's address and read the token straight back; that now happens only in development. The placeholder signing key published in this repository was the compose file's default, which made session cookies and member-card QR codes forgeable; known placeholders are now refused and each install generates and stores its own key. The announcement renderer let an author break out of a link and attach an event handler, turning permission to write communications into script running in a super admin's session. Sign-in, registration and the two endpoints that email an address chosen by an anonymous caller are now rate limited, so password guessing and mailbox flooding are bounded. Adds security response headers, derives the session cookie's `Secure` attribute from the site URL, and passes the Resend credentials through to the backend — the compose file never did, so configuring Resend in `.env` silently did nothing. Also: a payment term for recurring billing, release notes drafted automatically when a tag is pushed, five install-guide defects found by walking it on a real server, and seeded addresses moved off a domain someone else owns. **Breaking:** an install that relied on the placeholder signing key gets a fresh one on first start, which signs everyone out and invalidates member-card QR codes already issued | Done   |

### Planned

Priority-ordered, not yet versioned. Each becomes a versioned release when it ships, and the release claims the next semver number in order.

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

### Quick Start

Start backend services (Docker) and frontend dev server (local):

```bash
./scripts/dev.sh start all
```

Check status:

```bash
./scripts/dev.sh status
```

Stop everything:

```bash
./scripts/dev.sh stop all
```

### Dev Commands

| Command | Description |
|---------|-------------|
| `./scripts/dev.sh start all` | Start backend (Docker) + frontend (local) |
| `./scripts/dev.sh start backend` | Start only backend (API + DB in Docker) |
| `./scripts/dev.sh start frontend` | Start only frontend (Next.js local) |
| `./scripts/dev.sh stop all` | Stop all services |
| `./scripts/dev.sh restart all` | Restart all services |
| `./scripts/dev.sh status` | Show status of all services |
| `./scripts/dev.sh logs backend` | View API logs |
| `./scripts/dev.sh logs frontend` | View frontend logs (tail -f) |
| `./scripts/dev.sh logs worker` | View Celery worker logs |
| `./scripts/dev.sh logs beat` | View Celery beat (scheduler) logs |
| `./scripts/dev.sh seed` | Run initial database setup (interactive) |
| `./scripts/dev.sh seed test` | Seed with test accounts (no prompts) |
| `./scripts/dev.sh test` | Run backend tests |

`start all` brings up the Celery worker and beat along with the API and database. `worker` and `beat` are also valid targets for `start`, `stop` and `restart` if you need to control them on their own.

> **Adding a backend dependency?** Python dependencies are baked into the Docker image — `pyproject.toml` is not bind-mounted — so a new dependency will be missing from the running container until you rebuild it:
>
> ```bash
> docker compose -f backend/docker/docker-compose.yml build --no-cache api
> docker compose -f backend/docker/docker-compose.yml up -d --force-recreate api
> ```

### Service URLs

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8003
- **API Docs (Swagger)**: http://localhost:8003/api/docs
- **Database**: localhost:5433
- **Adminer** (DB UI): http://localhost:8181 (start with `--profile tools`)

### Log Files

- Frontend: `frontend/logs/dev-server.log`
- Backend: `docker compose -f backend/docker/docker-compose.yml logs -f api`

### First Time Setup

After starting the services, run the setup command to create initial data:

```bash
./scripts/dev.sh seed          # Interactive — the same setup every environment uses
./scripts/dev.sh seed test     # Fixed test accounts + sample data, for the e2e suite
```

`seed test` creates the accounts the Cypress suite signs in as, plus 4 sample activities with
modalities and prices, sample registrations, and ~22 extra members. The addresses and passwords
are a contract with the test suite rather than a seeding choice, so they live with it, in
[`e2e/cypress/support/commands.ts`](e2e/cypress/support/commands.ts).

> **`seed test` refuses to run outside development.** It plants fixed, repository-visible
> passwords, so it requires `APP_ENV=development` or `CI` and exits otherwise. For anything
> real, use the interactive setup — see
> [First-time setup](docs/getting-started/first-setup.md).

## Installation (Docker)

### Prerequisites

- Docker and Docker Compose installed
- Git (to clone the repo)

### Option A: Pre-built images (recommended)

Uses published images from [GitHub Container Registry](https://github.com/marcandreuf/memship/pkgs/container/memship-backend).

```bash
git clone https://github.com/marcandreuf/memship.git
cd memship

# Configure
cp .env.example .env
# Edit .env — at minimum change SECRET_KEY and DB_PASSWORD
# Set the image version:
#   IMAGE_TAG=0.1.3

# Pull and start all services (Caddy + API + Frontend + PostgreSQL)
docker compose pull
docker compose up -d

# Run the setup: super admin, club data reset, club setup
docker compose exec -it api python -m app.cli.seed

# Open http://localhost
```

### Option B: Build from source

Builds the Docker images locally from the repo source code.

```bash
git clone https://github.com/marcandreuf/memship.git
cd memship
cp .env.example .env
docker compose up -d --build
docker compose exec -it api python -m app.cli.seed
```

### Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost | Member portal (via Caddy) |
| API | http://localhost/api/v1/health | Backend API (via Caddy) |
| API Direct | http://localhost:8003 | Backend API (direct) |
| API Docs | http://localhost:8003/api/docs | Swagger UI (dev mode only) |

### Backups

```bash
# Create a backup
./scripts/db-backup.sh

# List and restore from a backup (dry-run by default)
./scripts/db-restore.sh

# Restore with confirmation
./scripts/db-restore.sh --confirm
```

Backups are stored in the `backups/` directory. Old backups are cleaned up after 10 days.

## Contributing

Memship is in its early stages. Code contributions will be welcome once the project foundation is in place — stay tuned.

In the meantime, feel free to [open an issue](https://github.com/marcandreuf/memship/issues) to share ideas, suggest features, or ask questions. All feedback is welcome.

## License

Memship is licensed under the [Elastic License 2.0 (ELv2)](LICENSE). You are free to use, modify, and self-host Memship. The license restricts offering it as a managed service to third parties.
