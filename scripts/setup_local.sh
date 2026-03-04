#!/usr/bin/env bash
# =============================================================================
# One-click local PostgreSQL setup for Niya FastAPI Template
# =============================================================================
# Prerequisites:
#   - PostgreSQL running locally (default: postgres@localhost:5432)
#   - psql on PATH
#   - .env file in the backend root (copy .env.example first)
# =============================================================================
set -euo pipefail

DB_NAME="${DB_NAME:-niya_dev}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Creating database '${DB_NAME}' (if it doesn't exist)..."
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -tc \
  "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
  psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -c \
  "CREATE DATABASE ${DB_NAME};"

echo "==> Running schema migrations..."
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
  -f "${SCRIPT_DIR}/setup.sql"

echo ""
echo "==> Done! Update DATABASE_URL in .env:"
echo "    DATABASE_URL=postgresql+asyncpg://${DB_USER}:PASSWORD@${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo ""
echo "==> Then start the API:"
echo "    python run.py"
