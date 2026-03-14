#!/bin/bash
set -e

# Wait for PostgreSQL if DATABASE_URL is set
if [ -n "$DATABASE_URL" ]; then
    /wait-for-postgres.sh
fi

# Run migrations if RUN_MIGRATIONS is set
if [ "$RUN_MIGRATIONS" = "1" ] || [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Running database migrations..."
    uv run alembic upgrade head
    echo "Migrations complete."
fi

exec "$@"
