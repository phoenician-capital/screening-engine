#!/bin/bash
# Quick redeploy script — pull latest and restart services
cd ~/screening-engine
git pull origin main
docker compose restart mcp-server frontend
echo "✅ Redeploy complete"
