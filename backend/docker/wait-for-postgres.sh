#!/bin/bash
set -e

# Extract host and port from DATABASE_URL
# Format: postgresql://user:pass@host:port/dbname
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')

DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-5432}

MAX_RETRIES=${MAX_RETRIES:-30}
RETRY_INTERVAL=${RETRY_INTERVAL:-1}

echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."

retries=0
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; do
    retries=$((retries + 1))
    if [ $retries -ge $MAX_RETRIES ]; then
        echo "ERROR: PostgreSQL not available after $MAX_RETRIES attempts"
        exit 1
    fi
    sleep "$RETRY_INTERVAL"
done

echo "PostgreSQL is ready."
