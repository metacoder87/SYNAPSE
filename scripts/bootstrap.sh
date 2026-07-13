#!/usr/bin/env bash
# SYNAPSE one-command bootstrap (macOS / Linux)
# Usage (from repo root):  bash scripts/bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== SYNAPSE Bootstrap ==="

# --- 1. Prerequisite checks
for tool in docker python3 node npm; do
  command -v "$tool" >/dev/null || { echo "MISSING PREREQUISITE: $tool"; exit 1; }
done
command -v ollama >/dev/null || {
  echo "WARNING: Ollama not found — deep-dive agents will not run."
  echo "         Install from https://ollama.com then: ollama pull llama3:8b"
}

# --- 2. Environment file
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from template — ADD YOUR API KEYS to .env"
fi

# --- 3. Containers
echo; echo "Starting containers..."
docker compose up -d

# --- 4. Backend
echo; echo "Setting up backend..."
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -e "./backend[dev]"
(cd backend && ../.venv/bin/alembic upgrade head)

# --- 5. Frontend
echo; echo "Setting up frontend..."
(cd frontend && npm install)

# --- 6. Done
cat << 'EOF'

=== Bootstrap complete ===

Start the app (two terminals):
  1. cd backend && source ../.venv/bin/activate && uvicorn app.main:app --reload
  2. cd frontend && npm run dev

Then:
  - Dashboard:   http://localhost:3000
  - API docs:    http://localhost:8000/docs
  - Grafana:     http://localhost:3001  (admin / synapse)
  - Phoenix:     http://localhost:6006

First-run checklist:
  1. Edit backend/profile/candidate_profile.md (this drives all matching!)
  2. curl -X POST http://localhost:8000/profile/refresh
  3. curl -X POST http://localhost:8000/ingest/run
EOF
