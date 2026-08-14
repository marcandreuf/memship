# Installation (Docker)

This guide covers a **production** self-hosted install. For a quick local evaluation, use the
[Quick start](quickstart.md) instead.

## Prerequisites

- A server running Docker Engine and the Compose plugin
- An ordinary (non-root) user in the `docker` group — the stack is not installed as root
- `git`, to clone this repository. Minimal server images often ship without it:
  `sudo apt-get update && sudo apt-get install -y git`
- A domain name, with a DNS A record already pointing at the server, if you want automatic HTTPS

### Starting from a bare server

`scripts/vps-bootstrap.sh` does the root half of the preparation. Run it **once, as root**, on a
fresh Debian 12 or Ubuntu 24.04 box:

Clone it somewhere you can already write — your own home directory. The final checkout lives
under `/srv`, but nothing can write there until the bootstrap has run:

```bash
git clone https://github.com/marcandreuf/memship.git ~/memship-bootstrap
sudo ~/memship-bootstrap/scripts/vps-bootstrap.sh --user deploy --ssh-key-file ~/.ssh/authorized_keys
```

`--user` names the account that will own the install; pass the account you are already logged in
as (`--user "$USER"`) to use it instead of creating a separate `deploy`. `--ssh-key-file` takes a
file containing an SSH **public** key — your own `~/.ssh/authorized_keys` is the reliable choice,
since a fresh server has no `.pub` file lying around. Without a key you cannot log in as the new
user. The `~` above is expanded by your own shell before `sudo` runs, so it is your home
directory; from a **root shell** (`sudo -i`) it would be root's, so pass an absolute path there.

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

As the deploy user — **not** as root. `/srv` belongs to root, so create the install directory and
hand it to yourself before cloning into it; `install.sh` writes `.env` inside the checkout and
needs to own it:

```bash
sudo install -d -o "$USER" -g "$USER" /srv/openmemship
git clone https://github.com/marcandreuf/memship.git /srv/openmemship/app
cd /srv/openmemship/app
./scripts/install.sh --data-root /srv/openmemship/data --domain memship.example.com
```

The bootstrap clone in your home directory has done its job now and can be deleted.

That creates the data root, generates real secrets into `.env` (mode 600), pulls the published
images and starts the stack.

**Your install is pinned to a version.** `install.sh` sets `IMAGE_TAG` to the most recent release
tag in the checkout, so the deployment stays on that version until you move it deliberately, and
`/api/v1/health` reports which one it runs. Pass `--tag 2.2.0` to pin a different one. To upgrade,
edit `IMAGE_TAG` in `.env` and re-run the script — see [Upgrading](../self-hosting/upgrading.md).

**Point DNS at the server first.** `install.sh` refuses to start when the hostname does not
resolve to this host, because Caddy validates over HTTP-01 and Let's Encrypt rate-limits *failed*
validations at 5 per hostname per hour — a premature start can lock you out of certificates for
an hour. Use `--skip-dns-check` only if you know why you are skipping it.

The script is safe to re-run. It never overwrites an existing `.env`, and re-running is how you
pick up a new `IMAGE_TAG` later.

> **Reinstalling from scratch burns certificates.** The issued certificate lives in
> `<data-root>/caddy/data`. Delete that directory — as a full teardown does — and the next start
> requests a **new** certificate rather than renewing the old one. Let's Encrypt allows **5
> certificates per week for the same set of hostnames**, so a handful of from-scratch reinstalls
> against one domain will exhaust it and leave you without HTTPS until the window rolls forward.
> When rehearsing an install, omit `--domain` and run on plain HTTP, then add the domain on the
> final pass. Preserving `caddy/data` across a rebuild avoids the reissue entirely.

Then run the setup — it creates your super admin and your organization:

```bash
docker compose exec -it api python -m app.cli.seed
```

The `-it` matters: the command prompts. See [First-time setup](first-setup.md) for what it
asks and for the unattended flags an automated deployment uses instead.

Open your domain — or, if you installed without one, **http://&lt;server-address&gt;**, the hostname or
IP you reach the box on. `localhost` only works when you are installing on the machine in front of
you.

### Without a domain

Omit `--domain`. Caddy then serves plain HTTP on port 80, which is what you want for a local or
internal install.

This is also how to rehearse an install on a real server without spending certificates: install
with no `--domain`, confirm the stack works, then re-run with `--domain` to add HTTPS. Re-running
updates `SITE_ADDRESS` and the public URLs together, so nothing is left pointing at the old
address.

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
- **`SECRET_KEY`** and **`DB_PASSWORD`** — random values, never the placeholders. `SECRET_KEY` may
  be left blank (the server generates one into `storage/session.key`), but setting it explicitly is
  what lets a rebuilt host keep working sessions and readable payment credentials
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

The default Compose stack runs behind a Caddy reverse proxy. These URLs are **as seen from the
server itself** — the API and database are bound to `127.0.0.1`, so `localhost` is the only way to
reach them. From anywhere else, use your domain or the server's address, which reaches the first
two rows only:

| Service    | URL (on the server)              | Description               |
|------------|----------------------------------|---------------------------|
| Frontend   | `http://localhost`               | Member portal (via Caddy) |
| API        | `http://localhost/api/v1/health` | Backend API (via Caddy)   |
| API Direct | `http://localhost:8003`          | Backend API (direct)      |

> **`ufw` does not constrain Docker.** Docker inserts its own iptables rules ahead of the
> firewall's, so a port published to all interfaces stays reachable from the internet even while
> `ufw` denies it. The shipped stack therefore publishes the API (8003) and Postgres (5433) on
> **`127.0.0.1` only**, which is why they are reachable from the server itself and nowhere else.
> Setting `API_BIND` or `DB_BIND` to `0.0.0.0` — or adding your own `ports:` entry — puts that
> service on the public internet regardless of your firewall rules. Verify from another machine
> with `nmap -Pn -p 22,80,443,5433,8003 <your-host>` rather than trusting `ufw status`.

## Next steps

1. [First-time setup](first-setup.md) — create your organization and admin.
2. [Configuration reference](../self-hosting/configuration.md) — review production settings.
3. [Email delivery](../self-hosting/email.md) — required for welcome emails, password resets,
   and payment notifications.
4. [Backups & restore](../self-hosting/backups-and-restore.md) — set up before going live.
