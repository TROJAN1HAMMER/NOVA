#!/bin/sh
set -e

echo "================================================================="
echo "  NOVA — Neural Orchestrated Vector Assistant Platform Startup   "
echo "================================================================="

# 1. Authoritative Schema Migrations via Alembic
echo "==> [1/3] Applying schema migrations..."
alembic upgrade head

# 2. Idempotent Baseline Seed (Initial run only, never overwrites or wipes)
echo "==> [2/3] Checking initial database baseline..."
python -m scripts.seed_all_screens_data --init-only

# 3. Application Startup
echo "==> [3/3] Launching NOVA FastAPI Application Server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
