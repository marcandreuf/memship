# Troubleshooting

Symptoms an operator actually hits, and what causes them. If something here is wrong or missing,
[open an issue](https://github.com/marcandreuf/memship/issues) — this page is built from real
installs, not from theory.

First, two commands worth running before anything else:

```bash
docker compose ps                       # what is up, and what is restarting
curl -s http://localhost/api/v1/health  # {"status":"healthy","version":"2.3.0",...}
```

`version` is the image tag you are on. If it reads `latest` you are on an unpinned install and
cannot tell what is running — set `IMAGE_TAG` in `.env` to a release and re-run
`./scripts/install.sh`.

## The stack will not start

### `Conflict. The container name "/memship-db" is already in use`

Another memship instance is already running on this host. The Compose file names its containers
explicitly, and those names are global to the Docker daemon, so a second copy collides even from a
different directory with a different data root and a different Compose project name.

```bash
docker ps -a --filter name=memship-      # find the other instance
```

Run the second instance on another host or VM. If the other one is dead and you want its name back,
`docker rm` the leftover containers.

### Containers restart in a loop, logs say permission denied

Almost always the data root. Docker creates a missing bind-mount source **as root**, and the
backend runs as your uid, so it cannot write into a directory Docker made for it:

```bash
ls -l "$MEMSHIP_DATA_ROOT"     # storage/ and celerybeat/ should be yours, postgres/ uid 70
sudo chown -R "$(id -u):$(id -g)" "$MEMSHIP_DATA_ROOT"/{storage,celerybeat,caddy,backups}
```

`postgres/` is different: mode `0700` owned by uid 70, unreadable by you. That is correct — read
the database with `./scripts/db-backup.sh`, not with `ls`.

If you are upgrading from a release where the backend ran as root, see the note in
[Upgrading](upgrading.md).

### Postgres will not start on RHEL, Fedora, Rocky or AlmaLinux

SELinux. Bind mounts need relabelling — see the SELinux section of
[Installation](../getting-started/installation.md).

### `port is already allocated`

Something else holds 80 or 443:

```bash
sudo ss -ltnp | grep -E ':(80|443)\b'
```

Stop it, or set `HTTP_PORT` / `HTTPS_PORT` in `.env` and recreate. Note that automatic HTTPS needs
port 80 reachable from the internet — Let's Encrypt validates over HTTP-01.

## It is running but I cannot reach it

**Check where you are looking from.** Every `localhost` URL in the docs is *from the server*. The
API and database are deliberately bound to `127.0.0.1`, so from your laptop only the frontend and
`/api/...` through the proxy are reachable, at the server's domain or IP.

**`ufw` does not constrain Docker.** Docker writes its iptables rules ahead of the firewall's, so a
port published on `0.0.0.0` stays internet-reachable even while `ufw` denies it. Verify from
another machine rather than trusting `ufw status`:

```bash
nmap -Pn -p 22,80,443,5433,8003 your-host
```

8003 and 5433 should be closed. If they are open, something set `API_BIND` or `DB_BIND` to
`0.0.0.0`, or added a `ports:` entry.

## HTTPS and certificates

### No certificate is issued

Caddy validates over HTTP-01, so the hostname must already resolve to this server and port 80 must
be open. `install.sh` refuses to start when DNS does not match, because failed validations are
rate-limited at 5 per hostname per hour.

### "Too many certificates already issued"

Let's Encrypt allows **5 certificates per week for the same set of hostnames**. The issued
certificate lives in `<data-root>/caddy/data`; deleting that directory — as a full teardown does —
makes the next start request a *new* certificate instead of renewing. Preserve `caddy/data` across
rebuilds, and rehearse installs without `--domain`.

### Security headers are missing after an upgrade

The `Caddyfile` is bind-mounted, so changing its contents does not change the running container's
configuration, and `docker compose up -d` sees no reason to recreate it:

```bash
docker compose ps caddy                          # "Up 3 days" after an upgrade is the tell
docker compose up -d --force-recreate caddy
curl -sI https://your-host/api/v1/health | grep -i -E 'content-security|x-frame|strict-transport'
```

Check the headers on an **API** path, not just the homepage. The frontend sets some of its own, so
`/` can look protected while every API response is bare.

## Setup and login

### `--admin-email needs the password in MEMSHIP_ADMIN_PASSWORD`

`docker compose exec` does not forward your shell's environment into the container. Name the
variable after `-e`:

```bash
MEMSHIP_ADMIN_PASSWORD='...' docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD \
  api python -m app.cli.seed --admin-email you@example.org
```

### Nobody can log in / the super admin password is lost

Reset it from the host with the same command. It is deliberately the only way in — there is no
recovery through the web interface for a super admin, and every reset is written to the audit log
with no acting user, since whoever ran it had shell access.

### The API refuses to start, complaining about `SECRET_KEY`

The placeholder key shipped in `.env.example` and the Compose default are published in this
repository, and they sign the session token, the member-card QR HMAC and the OAuth state — so they
are refused. Generate one:

```bash
openssl rand -hex 32
```

Leaving `SECRET_KEY` empty is allowed — the server generates and persists one — but setting it
explicitly is what lets a rebuilt host keep working sessions.

## Backups and restore

### A restore failed

The script leaves the API stopped on purpose. Starting it would run migrations against the
half-restored database and give you an instance that reports `"healthy"` and contains nothing.

Restore the pre-restore dump named in the failure message — not simply the newest one, which after
a second failed attempt is a copy of the already-damaged database.

### A restore says there is no terminal

The backup picker and the typed confirmation both need one. From a script or cron, name the dump
and pass `--yes`:

```bash
./scripts/db-restore.sh --confirm --yes memship_20260819_141405.sql.gz
```

### "Restore complete" but the data is gone

Releases before 2.3.0 could report success after a failed restore — `psql` ran without
`ON_ERROR_STOP`, so a corrupt or truncated dump emptied the database and still printed a green
result. Upgrade, and re-test your restores. A backup you have never restored is a guess.

## Logs

```bash
docker compose logs -f api             # backend, including migrations on startup
docker compose logs -f celery-worker   # scheduled jobs and email sending
docker compose logs -f caddy           # TLS issuance and proxying
docker compose logs --since 10m        # everything, recent
```

Celery is the component that fails quietly — if reminders or emails stop, look there first.
