# Memship - Development Guidelines

## Project Overview

Memship is a self-hosted membership management system for professional associations, sports clubs, and similar organizations. Licensed under Elastic License 2.0 (ELv2).

**Current version:** See `VERSION` file (pre-alpha)

**Tech stack (v0.1.0):**
- Backend: Python 3.12+ / FastAPI / SQLAlchemy 2.0 / Alembic
- Frontend: Next.js 16 / React 19 / Tailwind 4 / Shadcn/ui / next-intl
- Database: PostgreSQL 15 (single-tenant, `CHECK (id = 1)` on organization_settings)
- Package managers: uv (Python), pnpm (frontend)
- Containerization: Docker + Docker Compose
- CI: GitHub Actions
- Registry: GitHub Container Registry (ghcr.io)

## Commands

### Backend
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

### Frontend
```bash
cd frontend
pnpm install                     # Install dependencies
pnpm dev                         # Start dev server (localhost:3000)
pnpm build                       # Production build
pnpm lint                        # Run linter
```

### Docker (development)
```bash
cd backend/docker
docker compose up -d             # Start backend + db
docker compose --profile test up -d  # Include test db
docker compose --profile tools up -d # Include adminer
docker compose down              # Stop all
```

### Scripts
```bash
./scripts/bump-version.sh patch  # Bump patch version (0.0.1 → 0.0.2)
./scripts/bump-version.sh minor  # Bump minor version (0.0.1 → 0.1.0)
./scripts/bump-version.sh major  # Bump major version (0.0.1 → 1.0.0)
```

## Project Structure

```
memship/
├── VERSION                      # Semantic version (single source of truth)
├── CLAUDE.md                    # This file
├── README.md
├── LICENSE                      # ELv2
├── CONTRIBUTING.md
├── scripts/                     # Dev scripts (no Makefiles)
│   ├── bump-version.sh
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
│   │   ├── domains/             # Domain modules (models, schemas, services)
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
│   ├── features/                # Feature modules (auth, members)
│   ├── components/
│   │   ├── ui/                  # Shadcn components
│   │   └── layout/              # Header, sidebar, nav
│   ├── lib/                     # API clients, providers
│   └── locales/                 # Translation files (es, ca, en)
└── .github/
    └── workflows/
        ├── ci.yml
        └── build-images.yml
```

## Key Conventions

### General
- No Makefiles — use scripts in `scripts/`
- Version: single `VERSION` file at repo root, read by backend config and Docker builds
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
- Styling: Tailwind CSS with Shadcn CSS variables for theming

### Code Style
- Python: follow existing patterns, type hints on function signatures
- TypeScript: strict mode, prefer named exports
- Both: no unnecessary comments, no dead code, no over-engineering
