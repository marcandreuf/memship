# Memship - Development Guidelines

## Project Overview

Memship is a self-hosted membership management system for professional associations, sports clubs, and similar organizations. Licensed under Elastic License 2.0 (ELv2).

**Current version:** the latest `git tag` (`git describe --tags`) — git tags are the single source of truth; there is no VERSION file

## Product Strategy: MVP-first toward v1.0.0

Pre-1.0 development ships the **initial functional version** — broad enough that a club can manage members, activities, and basic billing end-to-end — then launches publicly with a landing page and live demo. Complex / in-depth variations of features are deferred past v1.0.0 and built ad-hoc when a real customer asks by name.

When scoping any feature before v1.0.0:
- Default to the initial-step version. Deeper variations are mentioned only as "could be added if a customer asks."
- Bundling three or more meaningful features in one version is a smell — split or trim.
- Per-provider depth is sugar when another path already covers the same user need. Defer.
- Don't add edge-case hardening that doesn't block normal flows.

Full strategic context lives in `memship-definition/CLAUDE.md` and `docs/STATUS.md`.

**Tech stack:**
- Backend: Python 3.12+ / FastAPI / SQLAlchemy 2.0 / Alembic
- Frontend: Next.js 16 / React 19 / Tailwind 4 / Shadcn/ui / next-intl / next-themes
- Database: PostgreSQL 15 (single-tenant, `CHECK (id = 1)` on organization_settings)
- Package managers: uv (Python), pnpm (frontend)
- Containerization: Docker + Docker Compose
- CI: GitHub Actions
- Registry: GitHub Container Registry (ghcr.io)

## Commands

### Dev Environment (recommended)
```bash
./scripts/dev.sh start all       # Start backend (Docker) + frontend (local)
./scripts/dev.sh stop all        # Stop everything
./scripts/dev.sh status          # Show status of all services
./scripts/dev.sh logs backend    # View API logs
./scripts/dev.sh logs frontend   # View frontend logs
./scripts/dev.sh seed            # Run initial setup (interactive)
./scripts/dev.sh test            # Run backend tests
./scripts/dev.sh start backend   # Start only backend (Docker)
./scripts/dev.sh start frontend  # Start only frontend (local)
```

### Backend (manual)
```bash
cd backend
uv sync                          # Install dependencies
uv run pytest -v                 # Run tests
uv run pytest -v --tb=short      # Run tests (short traceback)
python start.py                  # Start dev server (hot reload)
python -m app.cli.seed           # Run seed command (initial setup)
alembic upgrade head             # Run migrations
alembic revision --autogenerate -m "description"  # Create migration
```

### Frontend (manual)
```bash
cd frontend
pnpm install                     # Install dependencies
./dev.sh start                   # Start dev server (background, with logs)
./dev.sh stop                    # Stop dev server
./dev.sh status                  # Check if running
./dev.sh logs                    # Tail logs
pnpm build                       # Production build
pnpm lint                        # Run linter
```

### E2E (Cypress)
```bash
cd e2e
pnpm test:parallel:prod          # Full suite, 4 workers, production build (use this)
pnpm test:parallel               # Full suite against whatever is on :3000
pnpm cypress:run --spec 'cypress/e2e/auth/login.cy.ts'   # Single spec
```

**Run the full suite against a production build.** `next dev` compiles each
route on first request; with 4 workers sharing one dev server that stall pushes
navigations past their timeouts, so specs fail — or pass only on retry — and
which ones fail changes between runs. `test:parallel:prod` builds, serves, runs
and tears down. Measured on the same commit: 167/167 with no retries in 15m
against a production build, versus 165–166/167 with ~12 retry-only passes in
68m against the dev server.

Retries mask this, so read the failure screenshots in `cypress/screenshots/`
(gitignored, overwritten each run) — a screenshot with no "attempt N" suffix
means a test failed once and passed on retry. A clean run leaves none.

### Docker (backend services)
```bash
cd backend/docker
docker compose up -d             # Start backend + db
docker compose --profile test up -d  # Include test db
docker compose --profile tools up -d # Include adminer
docker compose down              # Stop all
```

### Scripts
```bash
./scripts/release.sh 1.3.0       # Tag a validated commit on main → triggers image promotion
./scripts/release.sh 1.3.0 <sha> # Tag a specific validated commit
```

## Project Structure

```
memship/
├── CLAUDE.md                    # This file
├── README.md
├── LICENSE                      # ELv2
├── CONTRIBUTING.md
├── scripts/                     # Dev scripts (no Makefiles)
│   ├── release.sh               # Tag a validated commit → triggers image promotion
│   └── dev.sh
├── backend/
│   ├── pyproject.toml           # Python deps (uv)
│   ├── start.py                 # Uvicorn entry point
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── core/                # Config, security, RBAC, pagination
│   │   ├── db/                  # SQLAlchemy base, session
│   │   ├── api/v1/              # API routes
│   │   │   └── endpoints/       # Including webhooks.py (POST /webhooks/{provider})
│   │   ├── domains/             # Domain modules (models, schemas, services)
│   │   │   ├── activities/      # Activities, modalities, prices, registrations, discounts, consents, attachments
│   │   │   ├── audit/           # Audit logging
│   │   │   ├── auth/            # Users, authentication
│   │   │   ├── billing/         # Receipts, concepts, mandates, remittances, payment providers, webhooks, Stripe, Redsys
│   │   │   │   └── providers/   # Payment provider adapters (Stripe, Redsys/Bizum, base)
│   │   │   ├── members/         # Members, membership types, groups
│   │   │   ├── organizations/   # Organization settings
│   │   │   └── persons/         # Persons, addresses, contacts
│   │   └── cli/                 # CLI commands (seed)
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   └── docker/
│       ├── Dockerfile
│       ├── docker-compose.yml
│       └── entrypoint.sh
├── frontend/
│   ├── package.json             # pnpm
│   ├── app/                     # Next.js app router
│   │   └── [locale]/            # i18n routes
│   ├── features/                # Feature modules
│   │   ├── activities/          # Activities, registrations, discounts, consents, attachments
│   │   ├── auth/                # Login, register, password reset
│   │   ├── groups/              # Group management
│   │   ├── members/             # Member CRUD
│   │   └── settings/            # Organization settings, membership types
│   ├── components/
│   │   ├── ui/                  # Shadcn components (sidebar, sheet, dropdown-menu, avatar, skeleton, breadcrumb, etc.)
│   │   ├── entity/              # Shared entity pattern (search, pagination, detail, tabs)
│   │   └── layout/              # Sidebar (Shadcn collapsible), header (SidebarTrigger + theme toggle), theme-toggle
│   ├── hooks/                   # Shared hooks (use-mobile)
│   ├── lib/                     # API clients, providers, status variants
│   └── locales/                 # Translation files (es, ca, en)
└── .github/
    └── workflows/
        ├── ci.yml                # Tests on PRs + main
        ├── build-images.yml      # RC images (sha-<commit>, main) after CI on main
        └── release.yml           # Promote RC → :X.Y.Z + :latest on tag push
```

## Key Conventions

### General
- No Makefiles — use scripts in `scripts/`
- Version: git tags are the single source of truth (no VERSION file). Images bake the tag in as the `APP_VERSION` build-arg/env; running from source falls back to `git describe`. Release by tagging a validated commit with `scripts/release.sh`
- Container naming: `memship-` prefix

### Backend
- Database naming: `snake_case`, plural tables (e.g., `members`, `activities`)
- API routes: `/api/v1/` prefix, versioned
- Domain modules: each domain has `models.py`, `schemas.py`, `service.py`
- Auth: JWT via HTTP-only cookies (set by Next.js API proxy, not directly by FastAPI)
- Password hashing: argon2
- Tests: pytest, integration tests use TestClient with real PostgreSQL

### Frontend
- i18n: next-intl, locales `es` (default), `ca`, `en` — never hardcode user-facing text
- State: TanStack Query for server state, React Context for auth — no Redux/Zustand
- Forms: React Hook Form + Zod validation
- API: server-side fetch via `lib/api-client.ts`, client-side via `lib/client-api.ts`
- Components: Shadcn/ui copied into `components/ui/`, fully customizable
- Layout: Shadcn Sidebar (collapsible, mobile sheet) + SidebarProvider + SidebarInset
- Dark mode: next-themes (ThemeProvider, attribute="class", system default)
- Styling: Tailwind CSS 4 with OKLCH CSS variables (teal brand palette)
- Tables: use `table-compact` CSS class for tab/supporting data tables

### Code Style
- Python: follow existing patterns, type hints on function signatures
- TypeScript: strict mode, prefer named exports
- Both: no unnecessary comments, no dead code, no over-engineering
