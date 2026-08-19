# Local development environment

The backend runs in Docker (API, Celery worker and beat, PostgreSQL, Redis); the frontend runs
locally with pnpm, so you get Next.js hot reload without a container in the way.

`scripts/dev.sh` drives all of it.

## Prerequisites

| Tool | Why |
|---|---|
| Docker Engine + Compose plugin | The backend stack |
| Node.js and **pnpm** | The frontend dev server |
| **uv** | Backend dependencies and the test run, which happen on the host rather than in a container |

## Start

```bash
./scripts/dev.sh start all      # backend in Docker + frontend locally
./scripts/dev.sh status         # what is up
./scripts/dev.sh stop all       # stop everything
```

> **The first `start all` on a clean machine can fail** with
> `failed to mkdir /var/lib/docker/volumes/docker_memship-storage/_data/<dir>: file exists`.
> The API, the Celery worker and beat all mount the same `memship-storage` volume and are created
> at the same time, so Docker's own volume setup races with itself. It is not a memship error and
> nothing is broken — **run the command again** and it starts cleanly. Only the first start on a
> given volume is affected.

## Commands

| Command | Description |
|---------|-------------|
| `./scripts/dev.sh start all` | Start backend (Docker) + frontend (local) |
| `./scripts/dev.sh start backend` | Start only the backend — API, DB, Redis, worker, beat |
| `./scripts/dev.sh start frontend` | Start only the Next.js dev server |
| `./scripts/dev.sh stop all` | Stop all services |
| `./scripts/dev.sh restart all` | Restart all services |
| `./scripts/dev.sh status` | Status of every service |
| `./scripts/dev.sh logs backend` | API logs |
| `./scripts/dev.sh logs frontend` | Frontend logs (`tail -f`) |
| `./scripts/dev.sh logs worker` | Celery worker logs |
| `./scripts/dev.sh logs beat` | Celery beat (scheduler) logs |
| `./scripts/dev.sh seed` | Interactive setup — the same one every environment uses |
| `./scripts/dev.sh seed test` | Fixed e2e test accounts and sample data |
| `./scripts/dev.sh test` | Backend test suite |
| `./scripts/dev.sh e2e` | Cypress, headless |
| `./scripts/dev.sh e2e:open` | Cypress GUI |
| `./scripts/dev.sh e2e:parallel` | Cypress, 4 workers |
| `./scripts/dev.sh reset` | **Destructive** — see below |

`start`, `stop` and `restart` take `backend`, `frontend`, `worker`, `beat` or `all` (the default).
`start all` brings up the worker and beat alongside the API and database.

> **`reset` deletes your volumes.** It runs `docker compose down -v`, which destroys the dev
> database *and* the storage volume — uploads and `storage/secret.key` with it. Losing that key
> means any payment-provider or SSO credentials stored in that database can no longer be
> decrypted. There is no confirmation prompt. Use it when you want a clean slate, not to fix a
> stuck container.

## Service URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8003 |
| API docs (Swagger) | http://localhost:8003/api/docs |
| Database | localhost:5433 |
| Test database | localhost:5434 (started by `dev.sh test`) |
| Redis | localhost:6379 |
| Adminer (DB UI) | http://localhost:8181 — not started by `dev.sh`, see below |

Adminer sits behind a Compose profile and has no `dev.sh` command:

```bash
docker compose -f backend/docker/docker-compose.yml --profile tools up -d adminer
```

## The dev stack is not hardened, and by default it is only on localhost

The dev stack ships deliberately weak settings: a fixed database password (`memship`), Redis with
no authentication, and — after `seed test` — **super admin credentials that are published in this
repository**. That is fine for a laptop and disastrous on a shared network, so the published ports
bind to `127.0.0.1` only.

If you need to reach the stack from another device — a phone testing the mobile layout, a VM —
override the bind address for that session:

```bash
DEV_BIND=0.0.0.0 ./scripts/dev.sh start backend
```

Do that only on a network you trust, and never on a stack seeded with `seed test`: those accounts
are in this repository, so anyone who can reach port 8003 can sign in as a super admin. The
frontend dev server binds to all interfaces on its own — that is Next.js's default and it serves no
data without the API.

## First-time setup

```bash
./scripts/dev.sh seed          # interactive, the same setup every environment uses
./scripts/dev.sh seed test     # fixed test accounts + sample data, for the e2e suite
```

`seed test` creates the accounts the Cypress suite signs in as, plus 4 sample activities with
modalities and prices, sample registrations, and ~22 extra members. Those addresses and passwords
are a contract with the test suite rather than a seeding choice, so they live with it in
[`e2e/cypress/support/commands.ts`](../../e2e/cypress/support/commands.ts).

> **`seed test` refuses to run outside development.** It plants fixed, repository-visible
> passwords, so it requires `APP_ENV=development` or `CI`. For anything real, use the interactive
> setup — see [First-time setup](../getting-started/first-setup.md).

## Tests

```bash
./scripts/dev.sh test     # backend suite: starts the test database, then pytest on the host
```

Roughly 1,270 tests, well under a minute. It runs `uv run pytest` from `backend/` against the
test database on port 5434, so backend dependencies must be installed on the host — `uv sync` in
`backend/` if it is a fresh checkout.

For end-to-end tests, **run the full suite against a production build**:

```bash
cd e2e && pnpm test:parallel:prod
```

`next dev` compiles each route on first request, and with 4 workers sharing one dev server that
stall pushes navigations past their timeouts — specs fail, or pass only on retry, and which ones
varies between runs. `test:parallel:prod` builds, serves, runs and tears down.

Retries mask failures, so read the screenshots in `e2e/cypress/screenshots/` (gitignored,
overwritten each run): a screenshot with no `attempt N` suffix means a test failed once and passed
on retry. A clean run leaves none. Intermittent retry-only passes under parallel load are a known
open problem — see [issue #58](https://github.com/marcandreuf/memship/issues/58).

## Adding a backend dependency

Python dependencies are baked into the image — `pyproject.toml` is **not** bind-mounted — so a new
dependency is missing from the running container until you rebuild:

```bash
docker compose -f backend/docker/docker-compose.yml build --no-cache api
docker compose -f backend/docker/docker-compose.yml up -d --force-recreate api
```

## Logs

| Where | How |
|---|---|
| Frontend | `frontend/logs/dev-server.log`, or `./scripts/dev.sh logs frontend` |
| Backend | `./scripts/dev.sh logs backend` |
| Celery | `./scripts/dev.sh logs worker` / `logs beat` |

Celery is the component that fails quietly. If scheduled billing or reminder emails stop, look
there before anywhere else.

## Working on the backend without Docker

```bash
cd backend
uv sync
uv run pytest -v
python start.py                                    # dev server, hot reload
python -m app.cli.seed                             # setup
alembic upgrade head                               # migrations
alembic revision --autogenerate -m "description"   # new migration
```

## Frontend directly

```bash
cd frontend
pnpm install
./dev.sh start      # background, with logs
./dev.sh stop
./dev.sh status
./dev.sh logs
pnpm build          # production build
pnpm lint
```
