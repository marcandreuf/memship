# Local development environment

The backend runs in Docker (API, Celery worker and beat, PostgreSQL, Redis); the frontend runs
locally with pnpm, so you get Next.js hot reload without a container in the way.

`scripts/dev.sh` drives all of it.

## Prerequisites

| Tool | Why |
|---|---|
| Docker Engine + Compose plugin | The whole backend — API, database, Redis, worker, beat, migrations and the test suite |
| **Node 22** and **pnpm** | The frontend dev server |

That is the complete list. **The backend never runs on the host**: no `uv sync`, no virtualenv, no
Python version to match, so the same checkout behaves the same on any machine with Docker.
`backend/app`, `backend/tests` and `backend/alembic` are bind-mounted into the containers — you
edit them in your editor and the running code changes. The container is where the code executes,
not where it lives.

Only the frontend stays on the host, and deliberately: the Next.js dev server is there for hot
reload, which is the one thing a container does not do as well. Cypress needs a real browser, so
the e2e suite is on the host too.

The Node major is pinned in `frontend/.nvmrc` and enforced as a warning by `engines` in
`frontend/package.json`. **Use 22** — it is what CI runs and what the production image is built on,
and a different major is the kind of difference that only shows up as a build that works on one
machine and not another. With `nvm`:

```bash
cd frontend
nvm install       # reads .nvmrc; `nvm use` on its own only switches to an already-installed major
corepack enable   # re-run this after every version switch — see below
```

A mismatch prints `WARN Unsupported engine` and carries on, which is deliberate — it should tell
you, not stop you mid-session. `pnpm install --engine-strict` turns the same check into a hard
failure if you ever want it enforced.

pnpm's version is pinned by `packageManager` in the same file, so `corepack enable` gets you the
right one without installing it yourself.

> **corepack shims live under each Node install**, so switching majors takes pnpm with it. If you
> arrive on 22 from another version, `./scripts/dev.sh start all` brings the backend up and then
> fails the frontend with `pnpm: command not found` in `frontend/logs/dev-server.log`. Running
> `corepack enable` once on the new major fixes it for good.

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
| `./scripts/dev.sh test [args]` | Backend test suite, in a container — extra arguments go to pytest |
| `./scripts/dev.sh shell` | A shell inside the API container |
| `./scripts/dev.sh migration "msg"` | Autogenerate an Alembic revision from your model changes |
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

## Email in dev

The dev stack dispatches nothing until a provider is configured — every send is logged and
skipped. Two ways in, and the first wins:

1. **Settings > Mailing** in the running app. It is stored in the database, so the API and the
   Celery worker both pick it up without a restart. Prefer it: it is the same path a self-hosting
   operator uses, and it is the only one the API container reads.
2. **`backend/.env`** — copy `backend/.env.example` and fill in `RESEND_API_KEY` or the `SMTP_*`
   block. The file is optional, no setup step creates it, and the worker reads it only if it is
   there. Its `DATABASE_URL` and `CELERY_BROKER_URL` are ignored inside the containers — the
   Compose `environment:` keys win — so the localhost values it ships with cannot break the stack.

Mind the asymmetry: mail sent straight from a request — password reset, email verification, the
Mailing screen's own test send — leaves the `api` container, which does not read `backend/.env`.
Only queued mail goes through the worker. Configure through the Mailing screen to exercise both.

## Tests

```bash
./scripts/dev.sh test                                # the whole backend suite
./scripts/dev.sh test tests/unit                     # one directory
./scripts/dev.sh test tests/unit/test_email.py -k layout   # anything else is passed to pytest
```

1,368 tests in about 40 seconds. They run in a throwaway `tests` container against `db-test`,
whose data directory is a tmpfs, so a run leaves nothing behind. Everything after `test` goes
straight to pytest.

The container points Celery at `redis://redis:6379/15` rather than the default. The suite enqueues
tasks — registering a member fires verification and confirmation emails — and the default broker
URL is `localhost:6379`, which on a host machine happens to be the dev Redis. So a host run was
publishing test-triggered tasks into the *dev* broker on database 0, where the dev worker picked
them up and ran them against the dev database. Database 15 has no consumer, so a task an assertion
provokes goes nowhere. (It is also what keeps the suite fast: with no listener at all, kombu retries
each publish for ~19 seconds — that alone took one file from 3s to 9m53s.)

That container is the only place the `dev` stage of `backend/docker/Dockerfile` is built. It
carries the `dev` extra — pytest, xdist, factory-boy — that the shipped image deliberately leaves
out, while the API, worker and beat containers keep building the production stage. So the stack
you develop against stays the one that ships, and the test dependencies never reach a registry.
`backend/tests` is bind-mounted, so an edited test runs immediately; only a dependency change
needs a rebuild.

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

Dependencies are installed into the image's virtualenv at build time, so a new one is missing from
the running containers until you rebuild. The test container is a separate build of a separate
stage, so it needs its own:

```bash
docker compose -f backend/docker/docker-compose.yml build --no-cache api
docker compose -f backend/docker/docker-compose.yml up -d --force-recreate api celery-worker celery-beat
docker compose -f backend/docker/docker-compose.yml --profile test build tests
```

`backend/pyproject.toml` *is* mounted into the test container, but only so pytest's own settings
follow the checkout. A mounted manifest installs nothing.

## Logs

| Where | How |
|---|---|
| Frontend | `frontend/logs/dev-server.log`, or `./scripts/dev.sh logs frontend` |
| Backend | `./scripts/dev.sh logs backend` |
| Celery | `./scripts/dev.sh logs worker` / `logs beat` |

Celery is the component that fails quietly. If scheduled billing or reminder emails stop, look
there before anywhere else.

## Migrations

The API container applies `alembic upgrade head` on every start, so a pulled migration is already
in your database by the time the container is up. Creating one:

```bash
./scripts/dev.sh migration "add attachment type allowlist"
```

It autogenerates against the running dev database and writes the revision into
`backend/alembic/versions` on the host. The command runs as **your** uid rather than the image's,
which is what makes the new file yours to edit — the container's built-in user is uid 1001, and
that is not the operator on every machine.

## Editor tooling

The backend runs in a container; your editor does not. Autocomplete, go-to-definition and inline
type checking need an interpreter that can resolve `fastapi`, `sqlalchemy` and the rest, and this
is the one reason a Python toolchain might still touch your machine:

- **Point the editor at the container** — VS Code Dev Containers or a JetBrains remote interpreter,
  against the `api` service. Nothing is installed on the host.
- **Keep a host virtualenv purely as a language-server target** — `cd backend && uv sync --extra dev`.
  Nothing ever runs from it: `dev.sh` does not read it, and neither do the tests.

Both are optional. The stack, the suite and the migrations all work with neither installed.

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
