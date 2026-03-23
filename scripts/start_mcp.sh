#!/bin/bash
set -e

echo "==> Starting MCP server on port ${PORT:-8000}..."
exec uvicorn src.mcp_server.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
