#!/bin/bash
set -e

echo "Running database migrations..."
python scripts/migrate.py

echo "Starting application..."
exec "$@"
