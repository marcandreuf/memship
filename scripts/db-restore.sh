#!/bin/bash
# Memship Database Restore
# Restores a PostgreSQL backup from the backups/ directory
# Usage: ./scripts/db-restore.sh [--dry-run|--confirm] [backup-file]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$REPO_ROOT/backups"
COMPOSE_FILE="$REPO_ROOT/docker-compose.yml"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

MODE="dry-run"
BACKUP_FILE=""

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --dry-run)  MODE="dry-run" ;;
        --confirm)  MODE="confirm" ;;
        *)          BACKUP_FILE="$arg" ;;
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
    read -p "Select backup number [1]: " choice < /dev/tty
    choice=${choice:-1}

    BACKUP_FILE="${BACKUPS[$choice]}"
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
    echo "  1. Stop the API container"
    echo "  2. Drop and recreate the memship_db database"
    echo "  3. Restore from: $(basename "$BACKUP_FILE")"
    echo "  4. Restart all containers"
    echo ""
    echo "To execute, run:"
    echo "  ./scripts/db-restore.sh --confirm $(basename "$BACKUP_FILE")"
    exit 0
fi

# Confirm mode — require explicit confirmation
echo -e "${RED}${BOLD}WARNING: This will DELETE all current data and restore from backup.${NC}"
echo ""
read -p "Type 'yes-restore-now' to confirm: " confirmation < /dev/tty

if [[ "$confirmation" != "yes-restore-now" ]]; then
    echo -e "${YELLOW}Restore cancelled${NC}"
    exit 0
fi

echo ""

# Check if containers are running
if ! docker compose -f "$COMPOSE_FILE" ps --status running 2>/dev/null | grep -q "memship-db"; then
    echo -e "${RED}x${NC} Database container is not running"
    echo "Start it with: docker compose up -d db"
    exit 1
fi

# Stop API to prevent connections during restore
echo -e "${BLUE}i${NC} Stopping API container..."
docker compose -f "$COMPOSE_FILE" stop api 2>/dev/null || true

# Drop and recreate database
echo -e "${BLUE}i${NC} Dropping and recreating database..."
docker compose -f "$COMPOSE_FILE" exec -T db \
    psql -U memship -d postgres -c "DROP DATABASE IF EXISTS memship_db;"
docker compose -f "$COMPOSE_FILE" exec -T db \
    psql -U memship -d postgres -c "CREATE DATABASE memship_db OWNER memship;"

# Restore from backup
echo -e "${BLUE}i${NC} Restoring from backup..."
gunzip -c "$BACKUP_FILE" | docker compose -f "$COMPOSE_FILE" exec -T db \
    psql -U memship -d memship_db --quiet

# Restart all services
echo -e "${BLUE}i${NC} Restarting services..."
docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo -e "${GREEN}=== Restore complete ===${NC}"
echo -e "  Restored from: $(basename "$BACKUP_FILE")"
echo ""
