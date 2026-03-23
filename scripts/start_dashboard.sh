#!/bin/bash
set -e

echo "==> Running database migrations..."
python scripts/migrate.py || echo "==> Migration warning (skipping)"

echo "==> Starting Streamlit dashboard on port ${PORT:-5000}..."
exec streamlit run src/dashboard/app.py \
    --server.port "${PORT:-5000}" \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false
