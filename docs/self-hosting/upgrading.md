# Upgrading

Memship is released as versioned Docker images, plus a handful of files that live beside them —
the Compose file, the Caddy configuration, the scripts. Upgrading means refreshing both, then
running one command that backs up, applies the version and verifies it. Database migrations run
automatically on startup.

## Versioning

Memship follows [semantic versioning](https://semver.org/). **Git tags are the single source
of truth** for the version — there is no `VERSION` file. Published images are tagged with the
release version (e.g. `2.7.1`) and `latest`.

Every install is pinned to a version rather than tracking `latest`, so upgrades are deliberate
and an instance can say which release it runs. `IMAGE_TAG` in `.env` holds it; `install.sh
--tag` and `upgrade.sh` write it for you, and `/api/v1/health` reports it back:

```bash
curl -s http://127.0.0.1:8003/api/v1/health
{"status":"healthy","version":"2.7.1","environment":"production"}
```

## Upgrade procedure

**Review the release notes** for the target version first — breaking changes and new required
settings are called out there, on the [releases page](https://github.com/marcandreuf/memship/releases).

Then two commands. Refresh the deployment files, then apply the version:

```bash
MEMSHIP_VERSION=2.7.1
cd /srv/openmemship/app          # wherever your install lives

curl -fsSL "https://github.com/marcandreuf/memship/archive/refs/tags/v${MEMSHIP_VERSION}.tar.gz" \
  | tar -xz --strip-components=1

./scripts/upgrade.sh "$MEMSHIP_VERSION"
```

**Why the first command.** Part of a release ships alongside the images rather than inside
them — `docker-compose.yml`, the `Caddyfile`, `scripts/`. Bumping `IMAGE_TAG` alone leaves an
install half-upgraded: the new backend running behind the old proxy configuration. Unpacking
over the directory replaces those files and leaves `.env` untouched, since `.env` is not in the
archive. No git and no source checkout are involved.

**What the second one does**, in order, stopping if any step fails:

1. **Backs up the database** with `scripts/db-backup.sh`. A release carrying a schema migration
   cannot be rolled back by re-pinning `IMAGE_TAG` — the images go back, the migrated schema
   does not — so this dump is the only way out of a bad upgrade. If it fails, the upgrade does
   not happen. On a first install there is no database yet and it says so instead.
2. **Applies the version** through `scripts/install.sh --tag "$MEMSHIP_VERSION"`, which writes
   `IMAGE_TAG`, pulls, and recreates the stack. It never overwrites an existing `.env`. It also
   force-recreates Caddy, which matters: the `Caddyfile` is bind-mounted, so changing its
   contents gives `docker compose up -d` no reason to recreate the container, and it would
   otherwise keep serving the old configuration.
3. **Verifies the result** with `scripts/verify-deployment.sh`, which waits for the API, checks
   that it reports the version you just deployed, and pings the Celery worker. `docker compose
   up -d` returning says only that containers were created — migrations run before the API
   serves, so a failed one looks like an API that never answers rather than a container that
   died.

This is the same command the deploy workflow runs over SSH, deliberately: what is automated and
what an operator types should not drift apart.

> The pre-upgrade dump lands in `$MEMSHIP_DATA_ROOT/backups`, on the same disk as the database
> it protects. It covers a bad upgrade, not a lost machine — see
> [Backups & restore](backups-and-restore.md#off-server-copies) for getting copies off the host.

## Upgrading from a release before the non-root backend

The backend containers used to run as root, so anything they wrote into the storage directory
landed root-owned. They now run as `HOST_UID`/`HOST_GID`, which is what makes bind-mounted
uploads readable on the host without `sudo` — but the container can no longer write the files
its root-era self left behind.

Take ownership once, after upgrading:

```bash
sudo chown -R $(id -u):$(id -g) "$MEMSHIP_DATA_ROOT/storage"
```

`scripts/install.sh` detects this and prints the exact command; running it by hand has the same
effect.

Two related changes in the same release:

- **`uv run` no longer works inside the containers.** The virtualenv is on `PATH` instead, so
  nothing under `/app` is written at runtime — that is what lets the container run under any uid.
  Use `docker compose exec api python -m …`, not `docker compose exec api uv run python -m …`.
  Anything you have scripted against the containers needs the same edit.
- **Persistent data moved from named volumes to bind mounts** under `MEMSHIP_DATA_ROOT`. If you
  are upgrading an install that used named volumes, copy each one across before starting:

  ```bash
  docker run --rm -v pgdata:/from -v /srv/openmemship/data/postgres:/to \
      alpine cp -a /from/. /to/
  ```

## Database migrations

Migrations run automatically on backend startup when `RUN_MIGRATIONS=1` (the default in the
Compose stack). No manual migration step is needed for a standard upgrade.

If you prefer to run migrations manually, set `RUN_MIGRATIONS=0` and run them yourself against
the backend container after pulling the new image.

## Rolling back

Roll back by re-running the upgrade against the older version — refresh the files from that
release's tarball, then `./scripts/upgrade.sh <older-version>`. Going back through the same path
you came in by keeps the deployment files and the images on the same release.

Note that **database migrations are not automatically reversed.** If the release you are leaving
included one, the images go back and the migrated schema does not, so restore the dump
`upgrade.sh` took before it applied that version — it is in `$MEMSHIP_DATA_ROOT/backups`, named
by timestamp — rather than only downgrading the image.
