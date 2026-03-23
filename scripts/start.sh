#!/bin/bash
set -e

# Run migrations only if DB vars are present
if [ -n "$DB_HOST" ] && [ -n "$DB_USER" ]; then
    echo "Running database migrations..."
    python scripts/migrate.py || echo "Migration warning (tables may already exist)"
else
    echo "No DB config — skipping migrations"
fi

echo "Starting application..."
exec "$@"
