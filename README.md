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

## Planned Features

**Member Management**
- Full member lifecycle: registration, onboarding, status changes, cancellation
- Membership types, groups, and custom fields
- Guardian/minor support
- Digital member card with QR code (mobile-friendly)

**Activities & Events**
- Activity creation with modalities, pricing, and capacity control
- Online registration with eligibility filters and waitlists
- Attendance tracking with QR check-in

**Payments & Invoicing**
- Membership fee generation and invoicing
- SEPA direct debit batch processing
- Stripe online payments
- Payment tracking and reminders

**Communications**
- Email campaigns with templates and audience targeting
- Direct messaging between admins and members
- Multi-language email templates

**Bookings & Spaces**
- Space and resource reservation system
- Calendar views with availability
- Booking rules and conflict prevention

**Reports & Dashboards**
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
| `./scripts/dev.sh test` | Run backend tests |

### Service URLs

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8003
- **API Docs (Swagger)**: http://localhost:8003/api/docs
- **Database**: localhost:5433

### Log Files

- Frontend: `frontend/logs/dev-server.log`
- Backend: `docker compose -f backend/docker/docker-compose.yml logs -f api`

### First Time Setup

After starting the services, run the seed command to create initial data:

```bash
./scripts/dev.sh seed
```

This will interactively prompt you for super admin and org admin credentials.

## Roadmap

| Version | Milestone | Status |
|---------|-----------|--------|
| v0.1.0 | Member Management MVP — auth, RBAC, member CRUD, membership types, i18n, Docker, CI | In progress |
| v0.1.x | Polish — email sending, restricted user role, groups, portal branding, self-hosted scripts, E2E tests | — |
| v0.2.0 | Activity Management | — |
| v0.3.0 | Basic Payments & Invoicing | — |
| v0.4.0 | Payment Processing (SEPA + Stripe) | — |
| v0.5.0 | Communication System | — |
| v0.6.0 | Bookings & Documents | — |
| v0.7.0 | Reports & Analytics | — |
| v0.8.0 | Digital Member Card & QR Check-in | — |
| v1.0.0 | Stabilization & Release | — |

## Contributing

Memship is in its early stages. Code contributions will be welcome once the project foundation is in place — stay tuned.

In the meantime, feel free to [open an issue](https://github.com/marcandreuf/memship/issues) to share ideas, suggest features, or ask questions. All feedback is welcome.

## License

Memship is licensed under the [Elastic License 2.0 (ELv2)](LICENSE). You are free to use, modify, and self-host Memship. The license restricts offering it as a managed service to third parties.
