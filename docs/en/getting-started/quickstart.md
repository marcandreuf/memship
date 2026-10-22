# Quick start

Try Memship on your machine in about a minute — no cloning required. This uses pre-built
images and is meant for **evaluation**, not production. For a real deployment, see
[Installation](installation.md).

## Prerequisites

- Docker and Docker Compose

## 1. Make a folder for it

Everything below runs from one directory, which ends up holding the single file this
needs. Compose takes its **project name** from that directory's name, and the quick-start
stack keeps its data in Docker volumes named after that project — so run every
`docker compose` command in this guide from inside this folder. From anywhere else Compose
looks for a different project and will not find your containers or your data.

```bash
mkdir -p "$HOME/memship-quickstart"
cd "$HOME/memship-quickstart"
```

## 2. Download the quick-start compose file and start

```bash
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml
docker compose pull          # fetch the latest published images
PORT=8081 docker compose up -d
```

Change `PORT=8081` to any port you prefer (default is `80`).

## 3. Run the setup

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

## 4. Open the app

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

## Stop everything

Run these from the folder you created in step 1 — Compose identifies the stack by the
directory it is run from.

```bash
docker compose stop          # pause it; containers and data stay put
docker compose start         # ... and pick up where you left off
```

```bash
docker compose down          # stop and remove the containers and the network; data kept
docker compose down -v       # ... and delete the data volumes with them
```

`down` keeps your database and uploads, so `docker compose up -d` afterwards brings back the
same club. **`down -v` is the one that leaves nothing behind** — the demo club, the super
admin you created and every receipt go with it, and there is no undo.

To get the disk space back as well, remove the images once the stack is down:

```bash
docker image rm ghcr.io/marcandreuf/memship-backend:latest \
                ghcr.io/marcandreuf/memship-frontend:latest
```

Leave `caddy`, `postgres` and `redis` alone unless you are sure nothing else on the machine
uses them — they are ordinary public images and something else may well.

### If you are not in that folder any more

The quick-start containers have fixed names, so you can always stop them by name from
anywhere — useful if you deleted the directory, or cannot remember where you put it:

```bash
docker rm -f demo-memship-caddy demo-memship-frontend demo-memship-api \
             demo-memship-celery-worker demo-memship-celery-beat \
             demo-memship-redis demo-memship-db
```

That removes the containers but not the data. The volumes are named after the Compose
project, which is the folder name — `docker volume ls | grep demo-memship` finds them, and
`docker volume rm <name>` deletes one.
