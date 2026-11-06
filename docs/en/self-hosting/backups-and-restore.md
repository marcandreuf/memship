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

### Do this on the day you install

`install.sh` generates `SECRET_KEY` and `MEMSHIP_SECRET_KEY` on the server, once, at first
install. They are never regenerated and no copy exists anywhere else — not in the repository,
not in your CI secrets, not in any dump. The install prints a warning saying so; it does not
print the values, because the same script runs from a deploy pipeline whose log may be public.

So before you put real data in, take `.env` off the server and put it somewhere that survives
the server:

```bash
scp -P <ssh-port> <user>@<host>:/srv/openmemship/app/.env  ~/memship-env-backup
```

Store it in a password manager, not only on your laptop, and give a second administrator
access. A recovery that depends on one person's machine stalls exactly when you need it.

This applies to a first deploy through the pipeline too — the pipeline creates `.env` on the
server the same way, and copies nothing back.

> **A file-level copy of `data/postgres` while the database is running is not
> crash-consistent.** For a dependable database backup use `db-backup.sh` below, which runs
> `pg_dump` inside the container. Use the `tar` copy for uploads, certificates and config — or
> stop the stack first if you want the whole tree in one consistent shot.

## Database backups

```bash
./scripts/db-backup.sh
```

The dump is written to `$MEMSHIP_DATA_ROOT/backups/` as a timestamped `.sql.gz`, mode `600` and
owned by the account that runs the script — it is a complete copy of your members' data, so it is
not left world-readable. Dumps older than 10 days are removed automatically.

For unattended backups, schedule it — nightly at 03:30, for example:

```cron
30 3 * * *  cd /srv/openmemship/app && ./scripts/db-backup.sh
```

That keeps the dumps on the same disk as the database. To get them off the server as well,
schedule `push-backup.sh` instead, which takes the dump itself: see
[Off-server copies](#off-server-copies).

> The script resolves the backup directory from `MEMSHIP_DATA_ROOT` in `.env`, the same way
> Compose does, so it always writes where the `db` container's `/backups` mount points. If you
> move the data root, both the backups and the script follow it — no second setting to update.

## Restore

The restore script lists the available dumps and lets you pick one. It is a **dry-run by
default**, so you can confirm the target before anything changes:

```bash
./scripts/db-restore.sh            # dry-run: shows what would happen
./scripts/db-restore.sh --confirm  # actually restore, asking you to type a confirmation
```

Both of those need a terminal — the picker and the confirmation both read from one. For a restore
run from a script, a cron job or a non-interactive `ssh host '…'`, name the dump and pass `--yes`:

```bash
./scripts/db-restore.sh --confirm --yes memship_20260819_141405.sql.gz
```

> **Restoring overwrites the current database.** Check you are pointed at the environment you
> think you are.

Before it drops anything the script checks that the archive is readable and looks like a
`pg_dump` file, and dumps the current database to `memship_pre-restore_<timestamp>.sql.gz` in the
same directory. If the restore then fails part-way it says so, exits non-zero, and **leaves the API
stopped on purpose** — starting it would run migrations against the half-restored database and
leave you with an instance that answers "healthy" and contains nothing. Put back what you had with
the pre-restore dump it names.

> When several restores fail in a row, each one writes its own pre-restore dump — and the newest is
> the one taken from the already-damaged database. Restore the file the failure message named, not
> whichever is most recent.

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

The same is true of the pre-upgrade snapshot the deploy pipeline takes: `upgrade.sh` runs
`db-backup.sh` before applying a release, but that dump lands in `backups/` on the instance.
It covers a failed migration. It does not cover losing the machine, and a green deploy log is
not evidence that anything left the building.

### Pushing from the server

`scripts/push-backup.sh` runs on the instance. It takes a fresh dump and pushes one **snapshot**
to another machine:

```
memship-20261106T033000Z/
├── db.sql.gz    the pg_dump
├── env          .env: the keys that decrypt the credentials inside the dump
└── storage/     uploads, plus session.key and secret.key
```

Those are the three things that cannot be rebuilt once the server is gone. It does not copy
`data/postgres`; the dump is the consistent copy of the database.

The destination is `BACKUP_TARGET` in `.env`, either an SSH host or S3-compatible object storage.
The settings are listed in [Configuration](configuration.md#off-server-backups).

**A snapshot that exists is a whole one.** Over SSH, it is written as `memship-<stamp>.partial`
and renamed only after every file has arrived; `latest` then points at it. On S3, a `COMPLETE`
object is uploaded last. A run that fails part-way leaves an incomplete snapshot behind. Restore
ignores it, and a later run removes it.

**Retention.** After a successful push, snapshots older than `BACKUP_RETENTION_DAYS` (default 30)
are removed from the destination. This is separate from the 10 days of dumps kept locally in
`backups/`.

**Failure is loud.** Any error exits non-zero and prints `PUSH FAILED`, along with what was and was
not done, so a backup that stopped is not mistaken for one that works.

#### To another host over SSH

The backup host needs a user with a shell and `rsync`. Nothing else, and no root.

1. On the instance, create a key used only for backups:
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/memship-backup
   ```
2. On the backup host, add `~/.ssh/memship-backup.pub` to that user's `~/.ssh/authorized_keys`.
3. From the instance, connect once to accept the host key. The script runs SSH in batch mode,
   so it will never answer that prompt for you:
   ```bash
   ssh -i ~/.ssh/memship-backup backup@backup.example.org true
   ```
4. In `.env`:
   ```bash
   BACKUP_TARGET=ssh://backup@backup.example.org/srv/memship-backups
   BACKUP_SSH_KEY=/home/deploy/.ssh/memship-backup
   ```
   Add a port when it is not 22: `ssh://backup@backup.example.org:2222/srv/memship-backups`.

Unchanged uploads are hard-linked against the previous snapshot rather than sent and stored
again. A month of snapshots therefore costs one copy of `storage/` plus whatever changed.

#### To S3-compatible object storage

Works with AWS S3 and any compatible store (MinIO, Backblaze B2, Wasabi, OVH, Scaleway…). It
runs the official `amazon/aws-cli` image through Docker, which is already on the server, so
nothing has to be installed.

1. Create a bucket, and an access key allowed to put, list and delete objects under the prefix
   you will use, and nothing else.
2. In `.env`:
   ```bash
   BACKUP_TARGET=s3://club-backups/memship
   BACKUP_S3_ACCESS_KEY_ID=…
   BACKUP_S3_SECRET_ACCESS_KEY=…
   BACKUP_S3_REGION=eu-west-1
   # Only for a store that is not AWS:
   BACKUP_S3_ENDPOINT=https://s3.eu-central-003.backblazeb2.com
   ```

The secret reaches the container through the environment, never on a command line.

#### Schedule it

`push-backup.sh` takes its own dump, so it replaces the nightly `db-backup.sh` line rather than
running beside it:

```cron
MAILTO=admin@example.org
30 3 * * *  cd /srv/openmemship/app && ./scripts/push-backup.sh
```

`MAILTO` only reaches you if the server can send mail. A check-in service is more reliable. It
alerts you when the ping **stops** arriving, which also covers cron itself not running:

```cron
30 3 * * *  cd /srv/openmemship/app && ./scripts/push-backup.sh && curl -fsS https://hc-ping.com/<your-uuid>
```

> **What you push contains everything.** `env` holds the keys and `db.sql.gz` holds every member
> record. Snapshots are not encrypted by memship. Give the destination the same protection as
> the server: a dedicated user or key, no public access to the bucket, and server-side
> encryption on the bucket where the store offers it.

### Restoring from a pushed snapshot

Use a complete snapshot: over SSH, the one `latest` points at (or any directory not ending in
`.partial`); on S3, one that contains `COMPLETE`.

1. Install a new server as in [Restoring onto a new server](#restoring-onto-a-new-server), steps
   1–2.
2. Fetch the snapshot onto it:
   ```bash
   # SSH
   rsync -a backup@backup.example.org:/srv/memship-backups/latest/ ~/restore/
   # S3, using the same image the push used
   docker run --rm -v ~/restore:/restore -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY        amazon/aws-cli:2.27.0 s3 cp --recursive s3://club-backups/memship/memship-<stamp>/ /restore/
   ```
3. Put the pieces back. `.env` goes first, because the database is unreadable without it:
   ```bash
   cp ~/restore/env /srv/openmemship/app/.env
   rsync -a ~/restore/storage/ /srv/openmemship/data/storage/
   cp ~/restore/db.sql.gz /srv/openmemship/data/backups/memship_<YYYYMMDD_HHMMSS>.sql.gz
   ```
   Name the dump after the snapshot. Any name starting `memship_` works. For a store that is
   not AWS, add `--endpoint-url <BACKUP_S3_ENDPOINT>` after the image name in the `docker run`.
4. `docker compose up -d db`, then
   `./scripts/db-restore.sh --confirm --yes memship_<YYYYMMDD_HHMMSS>.sql.gz`, then
   `docker compose up -d`.

Do this once against a scratch server before you rely on it.

### Pulling from your own machine

`scripts/pull-backup.sh` is the reverse: it runs on your workstation and pulls from the server. Use
it when the server should not hold credentials to anything else.

```bash
./scripts/pull-backup.sh <ssh-host> --dump              # fresh dump, then fetch .env + dumps
./scripts/pull-backup.sh <ssh-host> --with-data         # also uploads and TLS certificates
```

It needs root on neither machine, and it skips `data/postgres` for the same reason. It has no
schedule and no retention of its own: run it from cron on a machine that stays on, and point
`--dest` at storage that is itself backed up.
