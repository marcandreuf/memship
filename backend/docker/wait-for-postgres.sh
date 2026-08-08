#!/bin/bash
set -e

# Extract host, port and user from DATABASE_URL
# Format: postgresql://user:pass@host:port/dbname
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_USER=$(echo "$DATABASE_URL" | sed -n 's|^[^:]*://\([^:@/]*\).*|\1|p')

DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-5432}
# -U is not optional here. The container runs as ${HOST_UID}, the operator's own
# uid, which has no /etc/passwd entry — only the image's build-time `memship`
# user (1001) does. libpq derives its default username from getpwuid(), so
# without -U it cannot resolve one and gives up with exit 3 ("no attempt"),
# never contacting Postgres at all. The app itself is unaffected: its DSN names
# the user explicitly.
DB_USER=${DB_USER:-memship}

MAX_RETRIES=${MAX_RETRIES:-30}
RETRY_INTERVAL=${RETRY_INTERVAL:-1}

echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT as $DB_USER..."

retries=0
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -q; do
    retries=$((retries + 1))
    if [ $retries -ge $MAX_RETRIES ]; then
        echo "ERROR: PostgreSQL not available after $MAX_RETRIES attempts"
        exit 1
    fi
    sleep "$RETRY_INTERVAL"
done

echo "PostgreSQL is ready."
