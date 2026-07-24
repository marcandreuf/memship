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

3. **Bump the tag** in `.env`:

   ```bash
   IMAGE_TAG=1.3.0
   ```

4. **Pull and recreate:**

   ```bash
   docker compose pull
   docker compose up -d
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
