#!/bin/bash
# Memship Database Backup
# Creates a compressed PostgreSQL backup in the backups/ directory
# Usage: ./scripts/db-backup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$REPO_ROOT/backups"
COMPOSE_FILE="$REPO_ROOT/docker-compose.yml"
RETENTION_DAYS=10

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Generate filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/memship_${TIMESTAMP}.sql.gz"

echo -e "${BLUE}=== Memship Database Backup ===${NC}"
echo ""

# Check if db container is running
if ! docker compose -f "$COMPOSE_FILE" ps --status running 2>/dev/null | grep -q "memship-db"; then
    echo -e "${RED}x${NC} Database container is not running"
    echo "Start it with: docker compose up -d db"
    exit 1
fi

# Run pg_dump inside the container and write to the bind-mounted /backups dir
BACKUP_NAME="memship_${TIMESTAMP}.sql.gz"
echo -e "${BLUE}i${NC} Creating backup..."
docker compose -f "$COMPOSE_FILE" exec -T db \
    sh -c "pg_dump -U memship -d memship_db --clean --if-exists | gzip > /backups/${BACKUP_NAME}"
BACKUP_FILE="$BACKUP_DIR/$BACKUP_NAME"

# Verify backup was created and has content
if [[ ! -f "$BACKUP_FILE" ]] || [[ ! -s "$BACKUP_FILE" ]]; then
    echo -e "${RED}x${NC} Backup failed — file is empty or missing"
    rm -f "$BACKUP_FILE"
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo -e "${GREEN}+${NC} Backup created: $(basename "$BACKUP_FILE") ($BACKUP_SIZE)"

# Cleanup old backups
DELETED=0
if [[ -d "$BACKUP_DIR" ]]; then
    while IFS= read -r -d '' old_backup; do
        rm -f "$old_backup"
        DELETED=$((DELETED + 1))
    done < <(find "$BACKUP_DIR" -name "memship_*.sql.gz" -mtime +$RETENTION_DAYS -print0)
fi

if [[ $DELETED -gt 0 ]]; then
    echo -e "${YELLOW}i${NC} Cleaned up $DELETED backup(s) older than $RETENTION_DAYS days"
fi

# Show summary
TOTAL=$(find "$BACKUP_DIR" -name "memship_*.sql.gz" | wc -l)
echo ""
echo -e "${GREEN}=== Backup complete ===${NC}"
echo -e "  File: $BACKUP_FILE"
echo -e "  Size: $BACKUP_SIZE"
echo -e "  Total backups: $TOTAL"
echo ""
