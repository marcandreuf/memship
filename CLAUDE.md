# Memship - Development Guidelines

## Project Overview

Memship is a self-hosted membership management system for professional associations, sports clubs, and similar organizations. Licensed under Elastic License 2.0 (ELv2).

**Current version:** the latest `git tag` (`git describe --tags`) — git tags are the single source of truth; there is no VERSION file

## Where things belong

Roadmap, pre-1.0 scope discipline and strategic context live in the private
`memship-context` repo (`docs/STATUS.md`) — that is the single source, and this
file previously carried a copy of it that had already drifted.

Meeting notes, idea and proposal documents, and strategy material belong there
too — never in this repo. `docs/` here is **functional and setup documentation
only**: how memship works and how to run it. This repo is public; that one is not.

## Tech stack

- Backend: Python 3.12+ / FastAPI / SQLAlchemy 2.0 / Alembic
- Frontend: Next.js 16 / React 19 / Tailwind 4 / Shadcn/ui / next-intl / next-themes
- Database: PostgreSQL 15 (single-tenant, `CHECK (id = 1)` on organization_settings)
- Package managers: uv (Python), pnpm (frontend)
- Containerization: Docker + Docker Compose
- CI: GitHub Actions
- Registry: GitHub Container Registry (ghcr.io)

## Commands

### Dev Environment (recommended)

Full reference: [docs/development/local-environment.md](docs/development/local-environment.md).

```bash
./scripts/dev.sh start all       # Start backend (Docker) + frontend (local)
./scripts/dev.sh stop all        # Stop everything
./scripts/dev.sh status          # Show status of all services
./scripts/dev.sh logs backend    # View API logs
./scripts/dev.sh logs frontend   # View frontend logs
./scripts/dev.sh seed            # Run initial setup (interactive)
./scripts/dev.sh seed demo       # Demo club with generated credentials (prefer this)
./scripts/dev.sh passwd          # Replace the super admin password with a generated one
./scripts/dev.sh test            # Run backend tests
./scripts/dev.sh start backend   # Start only backend (Docker)
./scripts/dev.sh start frontend  # Start only frontend (local)
```

### Backend (containers only)

The backend never runs on the host — no `uv sync`, no virtualenv, no host Python. `backend/app`,
`backend/tests` and `backend/alembic` are bind-mounted into the containers, so edit locally and the
running code changes.

```bash
./scripts/dev.sh test                     # Full backend suite (throwaway container, tmpfs db)
./scripts/dev.sh test tests/unit -x       # Everything after `test` is passed to pytest
./scripts/dev.sh shell                    # Shell in the API container
./scripts/dev.sh migration "description"  # Autogenerate an Alembic revision
```

The API container runs `alembic upgrade head` on start, so pulled migrations apply themselves.
Inside a container use `python` / `pytest` / `alembic` directly — **never `uv run`**, which needs
write access to `/app/.venv` and fails as the non-root runtime user.

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
and tears down. It serves the build the way the image does — the standalone
server, not `next start`, which Next refuses to combine with
`output: "standalone"` and which served a build no deployment runs (#206).

**`cypress/e2e/roles/` runs on a worker of its own.** `run-parallel.sh` splits
the suite in two: the `roles/` specs run serially on one pinned worker, and
everything else shares the remaining threads. The default count of 4 therefore
means one pinned worker beside a three-thread pool, not a four-way pool.

The pinning is load-bearing, not tidiness. `roles-feature-flag.cy.ts` turns
`features.custom_roles` off inside its tests and restores it only in
`afterEach`. That flag is global `organization_settings` state, not per-worker:
while it is off, `showUsersTab` in `app/[locale]/(portal)/settings/page.tsx` is
false and the Accounts tab is gone for **every** session. A concurrent
`role-assignment.cy.ts` then timed out reaching that tab and passed only on
retry (#216). A cypress-parallel thread runs one `cypress run` over its whole
list, so a thread is genuine serialisation — which is what makes this a fix and
not a reshuffle.

**The general rule this encodes:** a spec that mutates global
`organization_settings` — a feature flag, a locale, anything on the single
`id = 1` row — is mutating state every other worker can see. It needs to be
confined to the pinned worker alongside every spec that reads what it touches,
or it will surface as an unrelated spec failing intermittently somewhere else.
Only the `custom_roles` flag has been audited this way.

Measured 2026-09-16 at 219 tests, after the pinning: three consecutive runs, all
**219/219 leaving no screenshots at all**, at 262.6s, 277.6s and 300.2s of spec
wall clock plus the build. The pinned worker took 2:41–2:55 of that, well inside
the pool's ~4.5 minutes, so it is not near becoming the critical path. Worker
count is not worth tuning off these numbers: the spread between identical runs
is ~38s, wide enough to swallow any difference a thread more or less would make.

An earlier three-run measurement on the same day, before the pinning, also
reported no retries — and a later run on that same code left one. Three clean
runs show a race is gone; they do not show there are no others. The dev-server
comparison is older and has not been re-taken — when the suite was 167 tests it
produced ~12 retry-only passes in 68m. Treat that figure as historical and the
conclusion as current.

Every run above reused the previous run's database rather than reseeding, and
none degraded — but worker assignment shifts between runs, so a shared-state
collision may simply not have been scheduled. See #117; it is not fixed.

Retries mask all of this, so read the failure screenshots in
`cypress/screenshots/` (gitignored, overwritten each run) — a screenshot with no
"attempt N" suffix means a test failed once and passed on retry. A clean run
leaves none.

Intermittent retry-only passes under parallel load remain a known open problem —
see issue #58, which #216 narrowed rather than closed. Treat a run that only
passes on retry as a failure to explain, not a pass.

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
- **Commits are authored by a human maintainer, always.** AI-assisted work ends with a plain
  `Assisted-by: Claude Code (claude-opus-5)` line — **never** `Co-Authored-By:`, which GitHub
  parses as a real contributor and lists in the repository's Insights next to the maintainers, and
  no `Claude-Session:` URL, which publishes a session link in a public repo. Transparency about the
  tooling is wanted; attribution that reads as authorship is not. The `commit-msg` hook in
  `.githooks/` enforces it (`git config core.hooksPath .githooks`, once per clone) — a human
  co-author is never stripped.

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
- Navigation: `Link` and `useRouter` always come from `@/lib/i18n/routing`, never from
  `next/navigation` — the plain ones drop the locale prefix and bounce through middleware

### Entity views

Every entity in the app — members, activities, groups, spaces — is rendered by the same
two shells, assembled from `components/entity/`. A new list or detail page reuses them
rather than inventing chrome; Activities is the reference implementation.

**List** (`activities/page.tsx`):
- `h1.text-2xl.font-bold` + `<PageInfo>` + the primary action, on one row
- `<SearchInput>`, plus a status `<Select>` when the entity has states
- `<TableSkeleton>` while loading; an empty state as `div.py-8.text-center.text-muted-foreground`
- desktop `<div className="hidden md:block rounded-md border">` around the `<Table>`,
  rows `cursor-pointer` with `onClick={() => router.push(detail)}` — never an action column
  whose only job is to open the row
- mobile `<div className="space-y-3 md:hidden">` of `<Link>` cards
- `<Pagination>` when the endpoint paginates, `<ExportButton>` when an export exists

**Detail** (`activities/[id]/page.tsx`):
- `<DetailHeader>` — breadcrumbs, title, status badge, and the page-level actions.
  Destructive page-level actions are `variant="destructive"`
- `<InlineEditWrapper>` — the basic-info card. The edit form replaces the read view in
  place; an entity's own fields are never edited in a modal
- `<EntityTabs>` — everything that extends the entity. Tab tables use `table-compact`, an
  `Añadir X` button, and row-level `Editar` buttons that *do* open a `Dialog`. Pass `lazy`
  so a tab's queries wait until it is opened

Modals belong inside tabs, not on the entity itself. Lists whose endpoint returns every
row unpaginated (groups, spaces) filter client-side rather than growing a backend param.

### Code Style
- Python: follow existing patterns, type hints on function signatures
- TypeScript: strict mode, prefer named exports
- Both: no unnecessary comments, no dead code, no over-engineering
