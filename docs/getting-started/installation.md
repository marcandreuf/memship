# Installation (Docker)

This guide covers a **production** self-hosted install. For a quick local evaluation, use the
[Quick start](quickstart.md) instead.

## Prerequisites

- A server running Docker Engine and the Compose plugin
- An ordinary (non-root) user in the `docker` group — the stack is not installed as root
- A domain name, with a DNS A record already pointing at the server, if you want automatic HTTPS

### Starting from a bare server

`scripts/vps-bootstrap.sh` does the root half of the preparation. Run it **once, as root**, on a
fresh Debian 12 or Ubuntu 24.04 box:

```bash
git clone https://github.com/marcandreuf/memship.git /srv/openmemship/app
sudo /srv/openmemship/app/scripts/vps-bootstrap.sh --ssh-key-file ~/id_ed25519.pub
```

It creates the deploy user, installs Docker from Docker's own repository, enables
`unattended-upgrades`, `fail2ban` and `ufw`, sets the timezone, and adds a weekly image prune.

It deliberately does **not** harden SSH — it prints those commands instead, in an order that
keeps a working session open while you verify each step. A script cannot check that you can
still log in, and getting the order wrong locks you out of a server that may have no console.

Log out and back in afterwards, so the deploy user's `docker` group membership takes effect.

> **The `docker` group grants effective root.** Anyone who can run `docker` can mount `/` into a
> container and write anywhere on the host. The deploy user is a privileged account, not a
> sandbox.

## Install

As the deploy user — **not** as root:

```bash
cd /srv/openmemship/app
./scripts/install.sh --data-root /srv/openmemship/data --domain memship.example.com
```

That creates the data root, generates real secrets into `.env` (mode 600), pulls the published
images and starts the stack.

**Point DNS at the server first.** `install.sh` refuses to start when the hostname does not
resolve to this host, because Caddy validates over HTTP-01 and Let's Encrypt rate-limits *failed*
validations at 5 per hostname per hour — a premature start can lock you out of certificates for
an hour. Use `--skip-dns-check` only if you know why you are skipping it.

The script is safe to re-run. It never overwrites an existing `.env`, and re-running is how you
pick up a new `IMAGE_TAG` later.

Then run the setup — it creates your super admin and your organization:

```bash
docker compose exec -it api python -m app.cli.seed
```

The `-it` matters: the command prompts. See [First-time setup](first-setup.md) for what it
asks and for the unattended flags an automated deployment uses instead.

Open your domain (or **http://localhost** if you installed without one).

### Without a domain

Omit `--domain`. Caddy then serves plain HTTP on port 80, which is what you want for a local or
internal install.

## The data root

Everything that must survive a redeploy lives under one directory:

| Path             | Contents                                                        |
|------------------|-----------------------------------------------------------------|
| `postgres/`      | The database                                                     |
| `storage/`       | Uploads (logos, activity images, generated PDFs) **and `secret.key`** |
| `celerybeat/`    | The scheduler's state                                            |
| `caddy/data`     | ACME account key and issued TLS certificates                     |
| `caddy/config`   | Caddy's autosaved configuration                                  |
| `backups/`       | Database dumps written by `scripts/db-backup.sh`                 |

Backing up memship means backing up **that one directory, plus `.env`**. See
[Backups & restore](../self-hosting/backups-and-restore.md).

Three things worth knowing about it:

- These are bind mounts, not named volumes, so the data survives
  `docker compose down -v` and `docker system prune --volumes`.
- `storage/` is written by the backend running as your uid, so uploads are readable without
  `sudo`.
- `postgres/` is mode `0700` owned by uid 70 — visible as a path but not readable by you. That is
  correct and expected. Read the database with `scripts/db-backup.sh`, not with `ls`.

> **Do not put the data root inside a `0700` home directory.** Containers running as other users
> (Postgres uses uid 70) cannot traverse into it, and Postgres will refuse to start. `/srv` is the
> FHS location for service data and survives deleting the user.

### SELinux hosts (RHEL, Fedora, Rocky, AlmaLinux)

On SELinux-enforcing systems, bind mounts need relabelling or the containers get
"permission denied" despite correct ownership. Either add `:z` to each bind mount in
`docker-compose.yml`:

```yaml
- ${MEMSHIP_DATA_ROOT:-./data}/postgres:/var/lib/postgresql/data:z
```

…or relabel the tree once, which survives Compose upgrades:

```bash
sudo semanage fcontext -a -t container_file_t "/srv/openmemship/data(/.*)?"
sudo restorecon -Rv /srv/openmemship/data
```

Debian and Ubuntu hosts are unaffected.

## Installing by hand

If you would rather not use `install.sh`, the equivalent manual steps are:

```bash
git clone https://github.com/marcandreuf/memship.git
cd memship
cp .env.example .env
```

Then set, at minimum:

- **`MEMSHIP_DATA_ROOT`** — absolute path to the data root described above
- **`SECRET_KEY`** and **`DB_PASSWORD`** — random values, never the defaults
- **`MEMSHIP_SECRET_KEY`** — encrypts stored SSO and payment-provider credentials. Set it
  explicitly so a rebuilt host can still decrypt a restored backup
- **`HOST_UID`** / **`HOST_GID`** — your `id -u` and `id -g`, so bind-mounted uploads belong to you
- **`SITE_ADDRESS`** — your hostname for automatic HTTPS, or leave empty for plain HTTP
- **`IMAGE_TAG`** — pin a released version; see [Upgrading](../self-hosting/upgrading.md)

Create the directory tree, then start the stack:

```bash
mkdir -p "$MEMSHIP_DATA_ROOT"/{postgres,storage,celerybeat,caddy/data,caddy/config,backups}
docker compose pull
docker compose up -d
```

See the [Configuration reference](../self-hosting/configuration.md) for every available setting.

## Services

The default Compose stack runs behind a Caddy reverse proxy:

| Service    | URL                              | Description               |
|------------|----------------------------------|---------------------------|
| Frontend   | `http://localhost`               | Member portal (via Caddy) |
| API        | `http://localhost/api/v1/health` | Backend API (via Caddy)   |
| API Direct | `http://localhost:8003`          | Backend API (direct)      |

> **`ufw` does not constrain Docker.** Docker inserts its own iptables rules ahead of the
> firewall's, so a port published with `ports:` stays reachable from the internet even while `ufw`
> denies it — including the API on 8003 and Postgres on 5433. Verify from another machine with
> `nmap -Pn -p 22,80,443,5433,8003 <your-host>` rather than trusting the firewall rules.

## Next steps

1. [First-time setup](first-setup.md) — create your organization and admin.
2. [Configuration reference](../self-hosting/configuration.md) — review production settings.
3. [Email delivery](../self-hosting/email.md) — required for welcome emails, password resets,
   and payment notifications.
4. [Backups & restore](../self-hosting/backups-and-restore.md) — set up before going live.
