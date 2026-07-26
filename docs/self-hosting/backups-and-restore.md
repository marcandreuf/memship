# Backups & restore

Memship ships helper scripts for backing up and restoring the PostgreSQL database. Set up
backups **before** going live and test a restore at least once.

> **What to back up.** These scripts cover the **database**. Uploaded files (logos, activity
> images, generated PDFs) live in the storage volume (`STORAGE_LOCAL_PATH`, default `storage`).
> Include that volume in your server-level backup routine as well.

## Create a backup

```bash
./scripts/db-backup.sh
```

Backups are written to the `backups/` directory. Backups older than 10 days are cleaned up
automatically.

For unattended backups, schedule the script with cron, for example nightly:

```cron
0 3 * * *  cd /path/to/memship && ./scripts/db-backup.sh
```

## Restore

The restore script lists available backups and lets you pick one. It runs as a **dry-run by
default** so you can confirm the target before making changes:

```bash
./scripts/db-restore.sh            # dry-run: shows what would happen
./scripts/db-restore.sh --confirm  # actually restore
```

> **Restoring overwrites the current database.** Take a fresh backup first and make sure you
> are restoring into the intended environment.

## Off-server copies

The `backups/` directory lives on the same server as the database. For real disaster recovery,
copy backups off the server regularly (object storage, another host, etc.) so a server failure
does not take your only copy with it.
