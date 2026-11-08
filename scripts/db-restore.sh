#!/bin/bash
# Memship Database Restore
# Restores a PostgreSQL backup from the backups/ directory
# Usage: ./scripts/db-restore.sh [--dry-run|--confirm] [--yes] [backup-file]
#
# A restore drops the live database before it reads the dump, so a dump that
# turns out to be unreadable would leave nothing behind. Three things guard
# against that, in order: the archive is tested before anything is dropped, a
# pre-restore dump of the current database is taken, and psql runs with
# ON_ERROR_STOP=1 under `pipefail` so a failed load is reported as a failure
# instead of being announced as success.
#
# A load that worked is not yet a restore that worked: "complete" is only
# printed once the API answers, after the database password has been set to the
# one in .env (see below for why that is needed on a new server).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
# Compose runs from the deployment directory with no -f, so it reads the same
# files as every other script: docker-compose.yml, plus whatever COMPOSE_FILE in
# .env layers over it (the external-proxy overlay). Pinning -f here used to make
# a restore's `up -d` recreate the stack without the overlay, starting the
# bundled Caddy on 80/443 and dropping the proxy's routing.
cd "$REPO_ROOT"

# Must match db-backup.sh: backups live under the data root, which is what
# docker-compose.yml bind-mounts onto /backups in the db container.
DATA_ROOT="${MEMSHIP_DATA_ROOT:-}"
if [[ -z "$DATA_ROOT" && -f "$REPO_ROOT/.env" ]]; then
    DATA_ROOT="$(grep -E '^MEMSHIP_DATA_ROOT=' "$REPO_ROOT/.env" | tail -1 | cut -d= -f2- || true)"
fi
DATA_ROOT="${DATA_ROOT:-$REPO_ROOT/data}"
case "$DATA_ROOT" in
    /*) ;;
    *) DATA_ROOT="$REPO_ROOT/${DATA_ROOT#./}" ;;
esac
BACKUP_DIR="$DATA_ROOT/backups"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

MODE="dry-run"
BACKUP_FILE=""
ASSUME_YES=0

usage() {
    cat <<'EOF'
memship — restore the database from a dump in the data root's backups/ directory.

  ./scripts/db-restore.sh                        # dry run: pick a dump, show what would happen
  ./scripts/db-restore.sh --confirm              # restore, asking for typed confirmation
  ./scripts/db-restore.sh --confirm --yes FILE   # restore unattended (cron, scripted SSH)

  --dry-run   Show what would happen and exit. The default.
  --confirm   Actually restore.
  --yes       Skip the typed confirmation. Required when there is no terminal,
              and only meaningful together with --confirm and a named file.
  FILE        A dump in the backups directory, or an absolute path. Without one
              the script lists what it has and asks — which needs a terminal.

The current database is dumped to memship_pre-restore_<timestamp>.sql.gz before
anything is dropped, so a restore that goes wrong is recoverable.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --dry-run)      MODE="dry-run" ;;
        --confirm)      MODE="confirm" ;;
        --yes|--force)  ASSUME_YES=1 ;;
        -h|--help)      usage; exit 0 ;;
        -*)             echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
        *)              BACKUP_FILE="$arg" ;;
    esac
done

echo -e "${BLUE}=== Memship Database Restore ===${NC}"
echo ""

# If no backup file specified, list available backups
if [[ -z "$BACKUP_FILE" ]]; then
    echo -e "${BOLD}Available backups:${NC}"
    echo ""

    if [[ ! -d "$BACKUP_DIR" ]] || [[ -z "$(ls -A "$BACKUP_DIR"/memship_*.sql.gz 2>/dev/null)" ]]; then
        echo -e "${RED}x${NC} No backups found in $BACKUP_DIR"
        echo "Run ./scripts/db-backup.sh first."
        exit 1
    fi

    # List backups sorted by date (newest first)
    INDEX=1
    declare -a BACKUPS
    while IFS= read -r backup; do
        SIZE=$(du -h "$backup" | cut -f1)
        NAME=$(basename "$backup")
        echo "  $INDEX) $NAME ($SIZE)"
        BACKUPS[$INDEX]="$backup"
        INDEX=$((INDEX + 1))
    done < <(ls -t "$BACKUP_DIR"/memship_*.sql.gz)

    echo ""

    # The picker needs somewhere to read from. A scripted SSH command, a cron job
    # and a CI step all have no terminal, and a restore is exactly the kind of
    # thing that gets run that way — so say what to do instead of dying on
    # /dev/tty with a device error.
    # Testing -r /dev/tty is not enough: the device node exists and looks
    # readable even with no controlling terminal, and only the open fails.
    if ! : 2>/dev/null < /dev/tty; then
        echo -e "${RED}x${NC} No terminal to ask which backup to use."
        echo "Name one on the command line instead:"
        echo "  ./scripts/db-restore.sh --confirm --yes $(basename "${BACKUPS[1]}")"
        exit 1
    fi

    read -r -p "Select backup number [1]: " choice < /dev/tty
    choice=${choice:-1}

    BACKUP_FILE="${BACKUPS[$choice]:-}"
    if [[ -z "$BACKUP_FILE" ]]; then
        echo -e "${RED}x${NC} Invalid selection"
        exit 1
    fi
fi

# Resolve full path
if [[ ! "$BACKUP_FILE" = /* ]]; then
    if [[ -f "$BACKUP_DIR/$BACKUP_FILE" ]]; then
        BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
    fi
fi

# Verify backup exists
if [[ ! -f "$BACKUP_FILE" ]]; then
    echo -e "${RED}x${NC} Backup file not found: $BACKUP_FILE"
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo -e "${BOLD}Backup:${NC} $(basename "$BACKUP_FILE") ($BACKUP_SIZE)"
echo ""

# Dry-run mode — just show what would happen
if [[ "$MODE" == "dry-run" ]]; then
    echo -e "${YELLOW}DRY RUN — no changes will be made${NC}"
    echo ""
    echo "This would:"
    echo "  1. Check the archive is readable"
    echo "  2. Dump the current database alongside it, as a fallback"
    echo "  3. Stop the API container"
    echo "  4. Drop and recreate the memship_db database"
    echo "  5. Restore from: $(basename "$BACKUP_FILE")"
    echo "  6. Set the database password to DB_PASSWORD from .env"
    echo "  7. Restart all containers and wait for the API to answer"
    echo ""
    echo "To execute, run:"
    echo "  ./scripts/db-restore.sh --confirm $(basename "$BACKUP_FILE")"
    exit 0
fi

# Confirm mode — require explicit confirmation
if [[ "$ASSUME_YES" -eq 1 ]]; then
    echo -e "${YELLOW}!${NC} --yes given: restoring without confirmation."
else
    echo -e "${RED}${BOLD}WARNING: This will DELETE all current data and restore from backup.${NC}"
    echo ""

    if ! : 2>/dev/null < /dev/tty; then
        echo -e "${RED}x${NC} No terminal to confirm at. Pass --yes to restore unattended."
        exit 1
    fi

    read -r -p "Type 'yes-restore-now' to confirm: " confirmation < /dev/tty

    if [[ "$confirmation" != "yes-restore-now" ]]; then
        echo -e "${YELLOW}Restore cancelled${NC}"
        exit 0
    fi
fi

echo ""

# Check if containers are running
if ! docker compose ps --status running 2>/dev/null | grep -q "memship-db"; then
    echo -e "${RED}x${NC} Database container is not running"
    echo "Start it with: docker compose up -d db"
    exit 1
fi

# Check the archive BEFORE dropping anything. A truncated or half-copied dump is
# the common case, and finding out after the drop is what turns a bad backup
# into a lost database.
echo -e "${BLUE}i${NC} Checking the archive..."
if ! gunzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo -e "${RED}x${NC} $(basename "$BACKUP_FILE") is not a readable gzip archive."
    echo "Nothing has been changed. Pick another dump."
    exit 1
fi
# Read the head into a variable rather than piping straight into grep: `head`
# closing the pipe early kills gunzip with SIGPIPE, and under `pipefail` that
# would fail the check on a perfectly good dump.
DUMP_HEAD="$(gunzip -c "$BACKUP_FILE" 2>/dev/null | head -c 65536 || true)"
if ! grep -q "PostgreSQL database dump" <<<"$DUMP_HEAD"; then
    echo -e "${RED}x${NC} $(basename "$BACKUP_FILE") does not look like a pg_dump file."
    echo "Nothing has been changed."
    exit 1
fi

# Take a fallback dump of what is about to be destroyed. Named memship_* so
# db-backup.sh's retention sweep ages it out like any other dump.
SAFETY_NAME="memship_pre-restore_$(date +"%Y%m%d_%H%M%S").sql.gz"
echo -e "${BLUE}i${NC} Dumping the current database first (${SAFETY_NAME})..."

# Same ownership dance as db-backup.sh: the db container writes as root, and this
# script has to be able to read the dump back off the host to undo a bad restore.
HOST_UID_VAL="${HOST_UID:-}"
HOST_GID_VAL="${HOST_GID:-}"
if [[ -f "$REPO_ROOT/.env" ]]; then
    HOST_UID_VAL="${HOST_UID_VAL:-$(grep -E '^HOST_UID=' "$REPO_ROOT/.env" | tail -1 | cut -d= -f2- || true)}"
    HOST_GID_VAL="${HOST_GID_VAL:-$(grep -E '^HOST_GID=' "$REPO_ROOT/.env" | tail -1 | cut -d= -f2- || true)}"
fi
HOST_UID_VAL="${HOST_UID_VAL:-$(id -u)}"
HOST_GID_VAL="${HOST_GID_VAL:-$(id -g)}"

if docker compose exec -T db \
        sh -c "pg_dump -U memship -d memship_db --clean --if-exists | gzip > /backups/${SAFETY_NAME} \
               && chown ${HOST_UID_VAL}:${HOST_GID_VAL} /backups/${SAFETY_NAME} \
               && chmod 600 /backups/${SAFETY_NAME}" \
   && [[ -s "$BACKUP_DIR/$SAFETY_NAME" ]]; then
    echo -e "${GREEN}+${NC} Fallback saved: $SAFETY_NAME"
    SAFETY_FILE="$BACKUP_DIR/$SAFETY_NAME"
else
    # An unreadable current database is a reason to restore, not to refuse.
    echo -e "${YELLOW}!${NC} Could not dump the current database — continuing without a fallback."
    rm -f "$BACKUP_DIR/$SAFETY_NAME"
    SAFETY_FILE=""
fi

# Stop API to prevent connections during restore
echo -e "${BLUE}i${NC} Stopping API container..."
docker compose stop api 2>/dev/null || true

# Drop and recreate database
echo -e "${BLUE}i${NC} Dropping and recreating database..."
docker compose exec -T db \
    psql -U memship -d postgres -c "DROP DATABASE IF EXISTS memship_db;"
docker compose exec -T db \
    psql -U memship -d postgres -c "CREATE DATABASE memship_db OWNER memship;"

# Restore from backup. ON_ERROR_STOP makes psql exit non-zero on the first failed
# statement; pipefail (set above) makes that the pipeline's status rather than
# gunzip's. Without both, a dump that fails every statement still reports success.
echo -e "${BLUE}i${NC} Restoring from backup..."
if ! gunzip -c "$BACKUP_FILE" | docker compose exec -T db \
        psql -U memship -d memship_db --quiet -v ON_ERROR_STOP=1; then
    echo ""
    echo -e "${RED}${BOLD}=== RESTORE FAILED ===${NC}"
    echo -e "  The dump did not load. The database is now incomplete."
    echo ""
    echo -e "  The API has been left stopped on purpose. Starting it would run"
    echo -e "  migrations against the half-restored database and leave you with a"
    echo -e "  healthy-looking, empty instance."
    echo ""
    if [[ -n "$SAFETY_FILE" ]]; then
        echo -e "  Put back what you had before this run:"
        echo -e "    ./scripts/db-restore.sh --confirm $(basename "$SAFETY_FILE")"
    else
        echo -e "  There is no fallback dump from this run — restore from another backup."
    fi
    echo ""
    exit 1
fi

# The role's password has to be .env's DB_PASSWORD, and after a restore onto a
# new server it is not. Postgres applies POSTGRES_PASSWORD only when it
# initialises its data directory, which there was install.sh's first start, with
# a freshly generated password; the old .env then goes back on top, and a
# pg_dump carries no roles. Every psql above goes through the local socket,
# which the image trusts, so the restore never notices. The API, worker and beat
# connect over TCP with the password and crash-loop (#552). A no-op when the two
# already match.
#
# Passed to the container by name, never by value: argv is readable by anyone on
# the host.
export MEMSHIP_RESTORE_DB_PASSWORD="${DB_PASSWORD:-}"
if [[ -z "$MEMSHIP_RESTORE_DB_PASSWORD" && -f "$REPO_ROOT/.env" ]]; then
    MEMSHIP_RESTORE_DB_PASSWORD="$(grep -E '^DB_PASSWORD=' "$REPO_ROOT/.env" | tail -1 | cut -d= -f2- || true)"
fi
# docker-compose.yml's own default, for an .env without one.
MEMSHIP_RESTORE_DB_PASSWORD="${MEMSHIP_RESTORE_DB_PASSWORD:-memship}"

echo -e "${BLUE}i${NC} Setting the database password to .env's DB_PASSWORD..."
if ! docker compose exec -T -e MEMSHIP_RESTORE_DB_PASSWORD db sh -c \
        'printf "%s\n" "ALTER ROLE memship PASSWORD :'\''pw'\'';" | psql -U memship -d postgres --quiet -v ON_ERROR_STOP=1 -v pw="$MEMSHIP_RESTORE_DB_PASSWORD"' \
        >/dev/null; then
    echo ""
    echo -e "${RED}${BOLD}=== RESTORE INCOMPLETE ===${NC}"
    echo -e "  The data from $(basename "$BACKUP_FILE") is in place, but the database"
    echo -e "  password could not be set to DB_PASSWORD from .env, so the API would"
    echo -e "  not be able to log in. It has been left stopped."
    echo ""
    exit 1
fi

# Restart all services
echo -e "${BLUE}i${NC} Restarting services..."
docker compose up -d

# `up -d` returning means the containers were created, not that the instance
# works: the API logs in to the database and applies migrations before it
# serves. Ask it, on the loopback port the way verify-deployment.sh does — the
# backend image has no curl to exec.
API_PORT="${API_PORT:-}"
if [[ -z "$API_PORT" && -f "$REPO_ROOT/.env" ]]; then
    API_PORT="$(grep -E '^API_PORT=' "$REPO_ROOT/.env" | tail -1 | cut -d= -f2- || true)"
fi
HEALTH_URL="http://127.0.0.1:${API_PORT:-8003}/api/v1/health"
TIMEOUT="${VERIFY_TIMEOUT:-300}"
echo -e "${BLUE}i${NC} Waiting for the API on $HEALTH_URL..."
deadline=$((SECONDS + TIMEOUT))
api_up=0
while [[ "$SECONDS" -lt "$deadline" ]]; do
    if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
        api_up=1
        break
    fi
    sleep 5
done
if [[ "$api_up" -eq 0 ]]; then
    echo ""
    echo -e "${RED}${BOLD}=== RESTORE INCOMPLETE: the API is not answering ===${NC}"
    echo -e "  The data from $(basename "$BACKUP_FILE") is in place, but the API did not"
    echo -e "  answer within ${TIMEOUT}s. Its last lines:"
    echo ""
    docker compose logs api --tail 20 --no-log-prefix 2>&1 | sed 's/^/    /' || true
    echo ""
    echo -e "  Check: docker compose ps; docker compose logs api"
    echo ""
    exit 1
fi

echo ""
echo -e "${GREEN}=== Restore complete ===${NC}"
echo -e "  Restored from: $(basename "$BACKUP_FILE")"
if [[ -n "$SAFETY_FILE" ]]; then
    echo -e "  Previous database kept as: $(basename "$SAFETY_FILE")"
fi
echo ""
