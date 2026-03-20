# Memship

> **This project is under active development, not yet ready for production, and open to [feature requests](https://github.com/marcandreuf/memship/issues).**

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

Try memship with a single command — no cloning required:

```bash
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml && PORT=8081 docker compose up -d
```

Then run the initial setup:

```bash
docker compose exec demo-memship-api uv run python -m app.cli.seed
```

Open http://localhost:8081 and log in with the credentials shown by the seed command. Change `PORT=8081` to any port you prefer (default is 80).

## Roadmap

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
| v0.2.2 | E2E test foundation (Cypress) — auth, members, activities, registrations | — |
| v0.2.3 | Activity polish — images, email notifications, loading skeletons, nuqs URL state | — |
| v0.3.0 | Basic Payments & Invoicing | — |
| v0.4.0 | Payment Processing (SEPA + Stripe) | — |
| v0.5.0 | Communication System | — |
| v0.6.0 | Bookings & Documents | — |
| v0.7.0 | Reports & Analytics | — |
| v0.8.0 | Digital Member Card & QR Check-in | — |
| v1.0.0 | Stabilization & Release | — |

---

## Features

**Member Management** (available now)
- Full member lifecycle: registration, onboarding, status changes, cancellation
- Membership types with groups, pricing, and age restrictions
- Guardian/minor support
- Role-based access: super admin, org admin, member
- Organization settings with branding (color, logo)
- Multi-language interface (ES, CA, EN) with locale selector in profile
- Admin dashboard with status charts (recharts)
- Unified entity pattern: list → detail → tabs for all entities

**Activities & Events** (available now)
- Activity creation with lifecycle management (draft → published → archived)
- Modalities (variants with independent capacity, pricing, and deadlines)
- Pricing tiers with time-based validity (early bird pricing)
- Online registration with eligibility checks (membership type, age, status)
- Capacity management with automatic waiting list and promotion
- Self-cancellation with configurable deadlines
- Discount codes (percentage/fixed, max uses, validity dates)
- Per-activity legal consents (mandatory/optional)
- Per-activity required attachments with file upload
- Member portal: activity browsing, registration, "My Activities" dashboard
- Admin portal: registration management with status changes

**Payments & Invoicing** (planned)
- Membership fee generation and invoicing
- SEPA direct debit batch processing
- Stripe online payments
- Payment tracking and reminders

**Communications** (planned)
- Email campaigns with templates and audience targeting
- Direct messaging between admins and members
- Multi-language email templates

**Bookings & Spaces** (planned)
- Space and resource reservation system
- Calendar views with availability
- Booking rules and conflict prevention

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
| `./scripts/dev.sh seed` | Run initial database setup (interactive) |
| `./scripts/dev.sh seed test` | Seed with test accounts (no prompts) |
| `./scripts/dev.sh test` | Run backend tests |

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

After starting the services, run the seed command to create initial data:

```bash
./scripts/dev.sh seed          # Interactive — prompts for admin credentials
./scripts/dev.sh seed test     # Quick — creates test accounts (no prompts)
```

The `seed test` option creates test accounts and sample data for development:

| Role | Email | Password |
|------|-------|----------|
| Super Admin | super@test.com | TestSuper1! |
| Org Admin | admin@test.com | TestAdmin1! |
| Member | member@test.com | TestMember1! |

Plus 5 extra member accounts (maria@test.com, joan@test.com, etc. / TestMember1!), 4 sample activities with modalities and prices, and sample registrations.

> **Warning:** Do not use test accounts in production. Use `./scripts/dev.sh seed` (interactive) for real deployments.

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

# Run initial setup (creates admin accounts)
docker compose exec -it api uv run python -m app.cli.seed

# Open http://localhost
```

### Option B: Build from source

Builds the Docker images locally from the repo source code.

```bash
git clone https://github.com/marcandreuf/memship.git
cd memship
cp .env.example .env
docker compose up -d --build
docker compose exec -it api uv run python -m app.cli.seed
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
