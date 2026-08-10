# Quick start

Try Memship on your machine in about a minute — no cloning required. This uses pre-built
images and is meant for **evaluation**, not production. For a real deployment, see
[Installation](installation.md).

## Prerequisites

- Docker and Docker Compose

## 1. Download the quick-start compose file and start

```bash
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml
docker compose pull          # fetch the latest published images
PORT=8081 docker compose up -d
```

Change `PORT=8081` to any port you prefer (default is `80`).

## 2. Load initial data

Pick one of the three seed modes:

**Option A — Quick demo with test accounts (no prompts)**

```bash
docker compose exec demo-memship-api python -m app.cli.seed --test
```

Creates pre-configured test accounts plus sample members, activities, and registrations:

| Role        | Email            | Password      |
|-------------|------------------|---------------|
| Super Admin | super@test.com   | TestSuper1!   |
| Org Admin   | admin@test.com   | TestAdmin1!   |
| Member      | member@test.com  | TestMember1!  |

**Option B — Custom setup (interactive)**

```bash
docker compose exec demo-memship-api python -m app.cli.seed
```

Prompts you to create your own super admin and org admin. No sample data.

**Option C — Realistic demo dataset**

```bash
docker compose exec demo-memship-api python -m app.cli.seed --demo
```

Creates the admin accounts plus a full year of realistic data — ~60 members across all
statuses, activities, receipts in every state, SEPA mandates, and dashboard reminders. Ideal
for evaluating the finance dashboard and annual summary. Safe to re-run (idempotent).

## 3. Open the app

Go to **http://localhost:8081** and log in with your credentials.

> **Do not use the test accounts in production.** The quick-start compose file uses a fixed
> database password and generates its signing key into the storage volume, and is for local
> evaluation only. See
> [Installation](installation.md) and the [Configuration reference](../self-hosting/configuration.md)
> before exposing Memship to a network.

## Stop and clean up

```bash
docker compose down          # stop containers
docker compose down -v       # stop and delete all data (volumes)
```
