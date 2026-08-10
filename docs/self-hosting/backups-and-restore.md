# Backups & restore

Set up backups **before** going live, and test a restore at least once. A backup you have never
restored is a guess, not a backup.

## What to back up

Two things, and you need both:

| What | Why |
|---|---|
| **The data root** (`MEMSHIP_DATA_ROOT`, e.g. `/srv/openmemship/data`) | The database, uploads, `secret.key`, `session.key`, TLS certificates — everything that must survive |
| **`.env`** | Your generated secrets. Losing `SECRET_KEY` and `MEMSHIP_SECRET_KEY` means losing access to encrypted data even with a perfect database dump |

Because every persistent path is a bind mount under one directory, backing memship up is copying
that directory:

```bash
sudo tar czf memship-$(date +%F).tar.gz \
    -C /srv/openmemship data \
    -C /srv/openmemship/app .env
```

`sudo` is needed because `data/postgres` is owned by uid 70 and mode `0700` — that is Postgres
protecting its own files, not a misconfiguration.

> **A file-level copy of `data/postgres` while the database is running is not
> crash-consistent.** For a dependable database backup use `db-backup.sh` below, which runs
> `pg_dump` inside the container. Use the `tar` copy for uploads, certificates and config — or
> stop the stack first if you want the whole tree in one consistent shot.

## Database backups

```bash
./scripts/db-backup.sh
```

The dump is written to `$MEMSHIP_DATA_ROOT/backups/` as a timestamped `.sql.gz`. Dumps older than
10 days are removed automatically.

For unattended backups, schedule it — nightly at 03:30, for example:

```cron
30 3 * * *  cd /srv/openmemship/app && ./scripts/db-backup.sh
```

> The script resolves the backup directory from `MEMSHIP_DATA_ROOT` in `.env`, the same way
> Compose does, so it always writes where the `db` container's `/backups` mount points. If you
> move the data root, both the backups and the script follow it — no second setting to update.

## Restore

The restore script lists the available dumps and lets you pick one. It is a **dry-run by
default**, so you can confirm the target before anything changes:

```bash
./scripts/db-restore.sh            # dry-run: shows what would happen
./scripts/db-restore.sh --confirm  # actually restore
```

> **Restoring overwrites the current database.** Take a fresh backup first, and check you are
> pointed at the environment you think you are.

## Restoring onto a new server

1. Run [`vps-bootstrap.sh` and `install.sh`](../getting-started/installation.md) as normal.
2. Stop the stack: `docker compose down`.
3. Restore `.env` from your backup — **the old one, not the newly generated one.** A fresh
   `MEMSHIP_SECRET_KEY` cannot decrypt SSO and payment-provider credentials stored in the old
   database.
4. Unpack the data root over the new one, keeping ownership: `sudo tar xzf … -C /srv/openmemship`.
5. `docker compose up -d`, then `./scripts/db-restore.sh --confirm` if you are restoring from a
   `pg_dump` rather than the directory copy.

## Off-server copies

The `backups/` directory sits on the same disk as the database it protects, so on its own it
survives nothing worse than a bad migration. Copy the dumps somewhere else on a schedule —
object storage, another host, anywhere with a different failure mode — or a single server loss
takes your only copy with it.
