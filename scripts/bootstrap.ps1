# SYNAPSE one-command bootstrap (Windows / PowerShell)
# Usage (from repo root):  .\scripts\bootstrap.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "=== SYNAPSE Bootstrap ===" -ForegroundColor Cyan

# --- 1. Prerequisite checks -------------------------------------------------
foreach ($tool in @("docker", "python", "node", "npm")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "MISSING PREREQUISITE: $tool" -ForegroundColor Red
        exit 1
    }
}
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "WARNING: Ollama not found — deep-dive agents will not run." -ForegroundColor Yellow
    Write-Host "         Install from https://ollama.com then: ollama pull llama3:8b"
}

# --- 2. Environment file ----------------------------------------------------
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from template — ADD YOUR API KEYS to .env" -ForegroundColor Yellow
}

# --- 3. Containers (Postgres, Chroma, Prometheus, Grafana, Phoenix) ---------
Write-Host "`nStarting containers..." -ForegroundColor Cyan
docker compose up -d

# --- 4. Backend ---------------------------------------------------------------
Write-Host "`nSetting up backend..." -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path "..\.venv")) { python -m venv ..\.venv }
& "..\.venv\Scripts\pip" install -e ".[dev]"
& "..\.venv\Scripts\alembic" upgrade head

# --- 5. Frontend --------------------------------------------------------------
Write-Host "`nSetting up frontend..." -ForegroundColor Cyan
Set-Location "$root\frontend"
npm install

# --- 6. Done ------------------------------------------------------------------
Set-Location $root
Write-Host @"

=== Bootstrap complete ===

Start the app (two terminals):
  1. cd backend ; ..\.venv\Scripts\activate ; uvicorn app.main:app --reload
  2. cd frontend ; npm run dev

Then:
  - Dashboard:   http://localhost:3000
  - API docs:    http://localhost:8000/docs
  - Grafana:     http://localhost:3001  (admin / synapse)
  - Phoenix:     http://localhost:6006

First-run checklist:
  1. Edit backend\profile\candidate_profile.md (this drives all matching!)
  2. POST http://localhost:8000/profile/refresh
  3. POST http://localhost:8000/ingest/run
"@ -ForegroundColor Green
