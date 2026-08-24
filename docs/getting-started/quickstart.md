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

## 2. Run the setup

The same command sets Memship up on every environment. It is interactive, and asks
three independent questions:

```bash
docker compose exec -it demo-memship-api python -m app.cli.seed
```

1. **Super admin** — you choose the address and password. Nothing is preset, and no
   credentials are published anywhere.
2. **Club data** — offered only when there is some, so on a fresh install it is a no-op.
3. **Club setup** — enter your organization's real details, or generate a demo club.

The three questions also have flags, for scripting an evaluation or running it where
there is no terminal to answer prompts:

```bash
# same three steps, unattended
docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD='...' demo-memship-api \
  python -m app.cli.seed --admin-email you@example.org
docker compose exec -T demo-memship-api python -m app.cli.seed --demo
```

Note `-T` instead of `-it`, and that the password goes through `docker compose exec -e`:
the container does not inherit your shell's environment, and passing it as an argument
would leave it in your shell history and in `ps`. `--reset-club-data` drives the third
question. See `python -m app.cli.seed --help`.

Answer **2) demo club** to look around with realistic data: ~60 members across all
statuses, activities, receipts in every state, SEPA mandates and dashboard reminders.
Ideal for evaluating the finance dashboard and annual summary. Safe to re-run
(idempotent).

The demo club also creates logins for a **club admin** and **two members**, with
generated passwords. They are printed once, at the end of the run:

```
  Accounts:

    super admin  you@example.org             (the password you chose)
    club admin   admin@mediterrani.example   4hVqTmXeb9PkscYRt2Nu
    member       demo0@mediterrani.example   pQ7yKdRfw3TgLmXaB6ns
    member       demo1@mediterrani.example   Zj5rWnEcx8VbHtPqM4dy
```

Keep that output — the passwords are stored only as hashes and cannot be shown again.

## 3. Open the app

Go to **http://localhost:8081** and log in as the super admin you created.

> **The quick-start stack is for evaluation, not for running a club.** Its compose file
> ships a fixed database password and keeps data in throwaway Docker volumes. Follow
> [Installation](installation.md) and the
> [Configuration reference](../self-hosting/configuration.md) before putting Memship on a
> network or entering real member data.

## Moving from evaluation to real use

Do not carry the quick-start stack into production — install it properly with
[Installation](installation.md), which generates real secrets and puts your data
somewhere you can back up.

If you only want to clear the demo club out of an instance you are keeping, re-run the
setup and answer *yes* to the club-data question. It deletes the demo club while keeping
your super admin, the system roles and any payment providers you configured — see
[First-time setup](first-setup.md).

## Stop and clean up

```bash
docker compose down          # stop containers
docker compose down -v       # stop and delete all data (volumes)
```
