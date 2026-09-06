# Upgrading

Memship is released as versioned Docker images. Upgrading means pointing at a newer image tag,
pulling, and recreating the stack — database migrations run automatically on startup.

## Versioning

Memship follows [semantic versioning](https://semver.org/). **Git tags are the single source
of truth** for the version — there is no `VERSION` file. Published images are tagged with the
release version (e.g. `1.2.0`) and `latest`.

Pin a specific version in production rather than tracking `latest`, so upgrades are
deliberate. Set it in `.env`:

```bash
IMAGE_TAG=1.2.0
```

## Upgrade procedure

1. **Back up first.** See [Backups & restore](backups-and-restore.md).

2. **Review the release notes** for the target version (breaking changes, new required
   settings) on the [releases page](https://github.com/marcandreuf/memship/releases).

3. **Refresh the deployment files, not only the image tag:**

   ```bash
   MEMSHIP_VERSION=1.3.0
   cd /srv/openmemship/app
   curl -fsSL "https://github.com/marcandreuf/memship/archive/refs/tags/v${MEMSHIP_VERSION}.tar.gz" \
     | tar -xz --strip-components=1
   ```

   Part of a release ships alongside the images rather than inside them —
   `docker-compose.yml`, the `Caddyfile`, `scripts/`. Bumping `IMAGE_TAG` alone leaves an
   install half-upgraded: the new backend running behind the old proxy configuration.

   Unpacking over the directory replaces those files and leaves `.env` untouched — it is not in
   the archive. The server needs no git and no source checkout for this.

4. **Bump the tag** in `.env`:

   ```bash
   IMAGE_TAG=1.3.0
   ```

5. **Pull and recreate:**

   ```bash
   docker compose pull
   docker compose up -d
   docker compose up -d --force-recreate caddy
   ```

   The last line matters. The `Caddyfile` is bind-mounted, so changing its contents does not
   change the container's configuration — `docker compose up -d` sees no reason to recreate
   Caddy and leaves it serving the old one.

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

Roll back by setting `IMAGE_TAG` to the previous version and recreating the stack. Note that
**database migrations are not automatically reversed** — if a release included a migration,
restore the database backup you took in step 1 rather than only downgrading the image.
