# Quick start

Try Memship on your machine in about a minute, no cloning required. This uses pre-built
images and is meant for **evaluation**, not production. For a real deployment, see
[Installation](installation.md).

> **En español:** [Prueba rápida](../../es/getting-started/quickstart.md).
> **En català:** [Inici ràpid](../../ca/getting-started/quickstart.md).

## Prerequisites

- Docker and Docker Compose

## 1. Make a folder for it

Everything below runs from one directory, which ends up holding the single file this
needs. Compose takes its **project name** from that directory's name, and the quick-start
stack keeps its data in Docker volumes named after that project, so run every
`docker compose` command in this guide from inside this folder. From anywhere else Compose
looks for a different project and will not find your containers or your data.

```bash
mkdir -p "$HOME/memship-quickstart"
cd "$HOME/memship-quickstart"
echo "STACK_PREFIX=$(date +%Y%m%d-%H%M%S)" > .env
```

That last line names this stack's containers after the moment you started it, so
`docker ps` tells you which evaluation is which and when you began it:
`20261105-043107-memship-api`. Compose reads `.env` from this folder on every command, so
you set it once. It also means a second evaluation in a second folder gets its own names
and can run alongside this one, on its own `PORT` and `MAILPIT_PORT`. Skip the line and
the containers are named `demo-memship-*`, which works until you want two.

## 2. Download the quick-start compose file and start

```bash
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml
docker compose pull          # fetch the latest published images
PORT=8081 docker compose up -d
```

Change `PORT=8081` to any port you prefer (default is `80`).

This runs the latest published images, and `/api/v1/health` reports `"version":"latest"`. To
evaluate a specific release instead, set `IMAGE_TAG` on both commands. Health then reports that
release:

```bash
IMAGE_TAG=3.1.0 docker compose pull
IMAGE_TAG=3.1.0 PORT=8081 docker compose up -d
```

## 3. Run the setup

The same command sets Memship up on every environment. It is interactive, and asks
three independent questions:

```bash
docker compose exec -it demo-memship-api python -m app.cli.seed
```

1. **Super admin**, you choose the address and password. Nothing is preset, and no
   credentials are published anywhere.
2. **Club data**, offered only when there is some, so on a fresh install it is a no-op.
3. **Club setup**, enter your organization's real details, or generate a demo club.

The three questions also have flags, for scripting an evaluation or running it where
there is no terminal to answer prompts:

```bash
# same three steps, unattended
docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD='...' demo-memship-api \
  python -m app.cli.seed --admin-email you@example.org
docker compose exec -T demo-memship-api python -m app.cli.seed --demo

# ... or --club-name instead of --demo, for the real-details path
docker compose exec -T demo-memship-api \
  python -m app.cli.seed --club-name 'Your Organization'
```

Note `-T` instead of `-it`, and that the password goes through `docker compose exec -e`:
the container does not inherit your shell's environment, and passing it as an argument
would leave it in your shell history and in `ps`. `--reset-club-data` drives the third
question. See `python -m app.cli.seed --help`.

### Which path to pick at question 3

**Evaluating Memship for the first time: answer `2) demo club`.** This is not only about
having data to look at. The demo club switches the optional modules **on**, and a
real-details install deliberately starts with almost all of them **off**: two of the
twenty-one feature keys, with seven routes redirecting to the dashboard. Choose real
details to see what Memship is, and the member card, the bookings calendar and
announcements are simply not there, with nothing on screen to say the module exists at
all. [Feature flags](../self-hosting/feature-flags.md) lists every one of them and how
each is switched on.

The demo club gives you ~60 members across all statuses, activities, receipts in every
state, SEPA mandates and dashboard reminders, which is enough to evaluate the finance
dashboard and the annual summary. Safe to re-run (idempotent).

The demo club also creates logins for a **club admin** and **two members**, with
generated passwords. They are printed once, at the end of the run:

```
  Accounts:

    super admin  you@example.org             (the password you chose)
    club admin   admin@mediterrani.example   4hVqTmXeb9PkscYRt2Nu
    member       demo0@mediterrani.example   pQ7yKdRfw3TgLmXaB6ns
    member       demo1@mediterrani.example   Zj5rWnEcx8VbHtPqM4dy
```

That is one interactive run answering all three questions. Driven by the flags above it is
two commands, and each prints only what it created: the super admin with the first, and
the club admin and the two members with the `--demo` run. The `--club-name` run creates no
logins, so it prints no accounts block at all.

Keep that output, the passwords are stored only as hashes and cannot be shown again.
The two member logins are how to see the member portal without handing out an admin
account, which is the half of the product an admin session never shows you.

**Answer `1) real details` only if you want to evaluate against your own data**, and read
this first:

> **A quick-start instance is not one to keep.** Whatever you enter, real or not, lives in
> throwaway Docker volumes behind a fixed database password, and by default every email
> the instance sends is caught by the local test inbox instead of reaching the person it
> is addressed to. That is what makes it safe to throw away, and what makes it wrong for a
> club. When you want an instance you keep, start again with
> [Installation](installation.md), which generates real secrets and puts your data
> somewhere you can back up.

## 4. Open the app

Go to **http://localhost:8081** and log in as the super admin you created.

> **Still an evaluation stack.** Before putting Memship on a network, follow
> [Installation](installation.md) and the
> [Configuration reference](../self-hosting/configuration.md). See
> [question 3 above](#which-path-to-pick-at-question-3) for why real member data does not
> belong here.

## 5. Try a member joining

The stack ships with a **test inbox** at **http://localhost:8025**. Every email the instance
sends, address verification, registration approval, receipts, payment reminders, lands
there instead of being delivered, whatever address it was sent to. This is the flow to try
first:

1. In a private window, open **http://localhost:8081/register** and sign up with any
   address, real or not.
2. Open the test inbox, find the verification email and follow its link.
3. Back in your admin session, open **Pending registrations** in the sidebar. The new sign-up
   is listed there, alongside a few the demo club seeds, so click **Approve** on its row and
   confirm.
4. The approval email arrives in the test inbox, and the member can now log in.

The inbox is local to your machine, it is published on `127.0.0.1` only, and holds nothing
real. Set `MAILPIT_PORT` alongside `PORT` if 8025 is taken.

It stays in effect **only while Settings → Mailing has never been saved**. Configure a real
provider there and that provider sends from then on, which is the intended precedence and not
a fault, see [Which one is in effect](../self-hosting/email.md#which-one-is-in-effect).

## Moving from evaluation to real use

Do not carry the quick-start stack into production, install it properly with
[Installation](installation.md), which generates real secrets and puts your data
somewhere you can back up.

A demo club has nine optional modules switched on because an evaluator should see them,
not because a club should run them. A real install starts with almost all of them off on
purpose, and you switch each one on when you are ready for it. Do not read the demo club's
configuration as a recommended one.

If you only want to clear the demo club out of an instance you are keeping, re-run the
setup and answer *yes* to the club-data question. It deletes the demo club while keeping
your super admin, the system roles and any payment providers you configured, see
[First-time setup](first-setup.md).

## Stop everything

Run these from the folder you created in step 1, Compose identifies the stack by the
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
same club. **`down -v` is the one that leaves nothing behind**, the demo club, the super
admin you created and every receipt go with it, and there is no undo.

To get the disk space back as well, remove the images once the stack is down:

```bash
docker image rm ghcr.io/marcandreuf/memship-backend:latest \
                ghcr.io/marcandreuf/memship-frontend:latest \
                axllent/mailpit:v1.29
```

Leave `caddy`, `postgres` and `redis` alone unless you are sure nothing else on the machine
uses them, they are ordinary public images and something else may well.

### If you are not in that folder any more

Every quick-start container carries `-memship-` in its name whatever prefix it was
started with, so you can find and stop one from anywhere, useful if you deleted the
directory or cannot remember where you put it:

```bash
docker ps -a --format '{{.Names}}' --filter name=-memship-   # which stacks exist
docker rm -f $(docker ps -aq --filter name=-memship-)        # remove all of them
```

The timestamp prefix is what tells the runs apart in that listing. The second command
removes every quick-start container on the machine, so check the first if you are running
more than one.

That removes the containers but not the data. The volumes are named after the Compose
project, which is the folder name, `docker volume ls | grep demo-memship` finds them, and
`docker volume rm <name>` deletes one.
