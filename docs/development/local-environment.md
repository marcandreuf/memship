# Local development environment

The backend runs in Docker (API, Celery worker and beat, PostgreSQL, Redis); the frontend runs
locally with pnpm, so you get Next.js hot reload without a container in the way.

`scripts/dev.sh` drives all of it.

## Prerequisites

| Tool | Why |
|---|---|
| Docker Engine + Compose plugin | The backend stack |
| **Node 22** and **pnpm** | The frontend dev server |
| **uv** | Backend dependencies and the test run, which happen on the host rather than in a container |

The Node major is pinned in `frontend/.nvmrc` and enforced as a warning by `engines` in
`frontend/package.json`. **Use 22** — it is what CI runs and what the production image is built on,
and a different major is the kind of difference that only shows up as a build that works on one
machine and not another. With `nvm`, `cd frontend && nvm use` picks it up.

A mismatch prints `WARN Unsupported engine` and carries on, which is deliberate — it should tell
you, not stop you mid-session. `pnpm install --engine-strict` turns the same check into a hard
failure if you ever want it enforced.

pnpm's version is pinned by `packageManager` in the same file, so `corepack enable` gets you the
right one without installing it yourself.

> **You do not need Node at all just to run memship.** The frontend ships as a container, and the
> [Quick start](../getting-started/quickstart.md) runs the whole app from published images in one
> command. Install the toolchain when you want to *work on* the frontend — the local dev server
> exists for hot reload, which is the one thing a container cannot do as well.

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
| `./scripts/dev.sh seed demo` | Demo club with **generated** credentials — prefer this |
| `./scripts/dev.sh seed test` | Fixed e2e test accounts, whose passwords are public |
| `./scripts/dev.sh passwd [email]` | Replace the super admin password with a generated one |
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

## The dev stack is not hardened — everything binds to localhost

The dev stack ships deliberately weak settings: a fixed database password (`memship`), Redis with
no authentication, and — after `seed test` — **super admin credentials that are published in this
repository**. That is fine on a laptop and disastrous on a shared network, so **nothing is exposed
beyond loopback by default**: the API, database, Redis and Adminer bind to `127.0.0.1`, and the
Next.js dev server does too.

Binding the containers is not enough on its own. Next.js binds `0.0.0.0` out of the box, and the
frontend proxies to the API server-side — so a dev server on every interface is a complete path
into the app, login included, even when every container is on loopback. Both halves are pinned.

### Working on a public network

Loopback binding is what makes a café or a co-working network safe, and it is the whole defence.
Layer the rest on top of it:

- **Prefer `./scripts/dev.sh seed demo`** over `seed test` for ordinary work. It seeds the same
  sample data but generates the super admin password and the demo logins, printing them once.
  `seed test` exists for the Cypress suite, whose credentials are a contract and therefore public.
- **If you have already run `seed test`**, `./scripts/dev.sh passwd` replaces the super admin
  password with a generated one. Re-running `seed test` puts the fixed ones back when you next
  need the suite.
- **Never combine `DEV_BIND=0.0.0.0` with `seed test` data.** Anyone on the network can then read
  the password out of this repository and sign in as super admin. `dev.sh start` checks for those
  accounts and warns you.

### Reaching the stack from another device

To test on a phone or from a VM, opt in for that session:

```bash
DEV_BIND=0.0.0.0 ./scripts/dev.sh start all
```

That publishes the containers on every interface and starts Next.js with `-H 0.0.0.0`. Do it only
on a network you control, and reseed with `seed demo` first.

### Platform notes

The `DEV_BIND` mechanism is Docker's own `HOST:PORT:PORT` syntax plus a Next.js flag, so it behaves
the same on all three platforms. What differs is what surrounds it:

| Platform | What to know |
|---|---|
| **Linux (Ubuntu 24.04+)** | Docker inserts its iptables rules **ahead of `ufw`**, so a published port is reachable even while the firewall denies it. `ufw` will not save you from `DEV_BIND=0.0.0.0` — the bind address is the control that works. |
| **macOS (Docker Desktop)** | Ports are forwarded by the VM to the host and the bind address is honoured, so loopback stays loopback. macOS may prompt for incoming connections the first time you use `dev:lan`. |
| **Windows (Docker Desktop + WSL2)** | Loopback binding works through WSL2's localhost forwarding. In **mirrored** networking mode (Windows 11, `networkingMode=mirrored` in `.wslconfig`) the WSL instance shares the host's interfaces, so `0.0.0.0` inside WSL is genuinely on the LAN — and Windows Firewall, not `ufw`, is what prompts. Run `dev.sh` from WSL or Git Bash; it is a bash script. |

`0.0.0.0` means *every* interface, which includes VPN and Tailscale adapters — those reach further
than the café's wifi.

## First-time setup

```bash
./scripts/dev.sh seed          # interactive, the same setup every environment uses
./scripts/dev.sh seed demo     # demo club, generated credentials — the everyday choice
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
