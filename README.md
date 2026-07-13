# Project SYNAPSE

**Systematic Yield Network for AI Placement & Strategic Employment**

A privacy-first, zero-API-cost, Human-in-the-Loop job intelligence system.
SYNAPSE autonomously ingests job market data from six sources, filters it
through a deterministic kill switch, ranks it by vector similarity against
your candidate profile, and — on demand — dispatches a local three-agent AI
crew to produce a fact-checked company dossier. All AI runs on your hardware
via Ollama; nothing about your search ever leaves your machine.

> PRD: `project_blueprint.md` · Build roadmap: `PROJECT_PLAN.md` · Version 1.0.0

## Architecture

```
USAJobs / Adzuna / Jooble / Greenhouse / Lever / RSS
        │  (adapter pattern → unified Job model)
        ▼
Regex Kill Switch ──discard──▶ logged, not stored
        ▼
MiniLM embeddings → Alignment Score (cosine vs your profile)
        ▼
PostgreSQL (source of truth) ⇄ ChromaDB (vectors, same UUIDs)
        ▼
Next.js cyberpunk dashboard ──"Deep Dive"──▶ CrewAI on Ollama
                                  Scout → Networker → Fact-Checker
```

Freshness is enforced three ways: daily deterministic expiry on closing
dates, a 12-hour heartbeat that probes live URLs (404s, generic redirects,
"position filled" text), and a weekly purge that removes stale rows from
Postgres and ChromaDB together.

## Quick Start

### Option A — everything in Docker (one command)

```
docker compose --profile app up -d --build
```

Builds and starts all seven containers: Postgres, ChromaDB, the FastAPI
backend (migrations run automatically), the Next.js dashboard, Prometheus,
Grafana, and Phoenix. First build takes several minutes (AI dependencies).
Requires Ollama running on the host (`ollama serve`). An ingest cycle fires
~20 seconds after boot. Note: don't run host-mode uvicorn/npm at the same
time — the ports collide.

### Option B — hybrid dev mode (hot reload)

```powershell
# Windows
.\scripts\bootstrap.ps1
```
```bash
# macOS / Linux
bash scripts/bootstrap.sh
```

The script checks prerequisites (Docker, Python 3.11+, Node 20+, Ollama),
creates `.env` from the template, starts all five containers, installs both
apps, and runs migrations. Then start two terminals:

```
cd backend  && uvicorn app.main:app --reload    # http://localhost:8000
cd frontend && npm run dev                       # http://localhost:3000
```

## Make It Yours (template customization)

Everything that personalizes SYNAPSE lives in four config surfaces — no code
changes required:

1. **`backend/profile/candidate_profile.md`** — the matching anchor. Every
   job is scored by cosine similarity against this text. Rewrite it for your
   target role, then `POST /profile/refresh`.
2. **`backend/filter_rules.yaml`** — kill-switch regexes (include/exclude/
   title-only-exclude). Edit, then `POST /filters/reload`.
3. **`.env`** — API keys, search keywords, Greenhouse/Lever company slugs,
   ingest interval, alignment threshold, model selection.
4. **`scripts/calibrate_threshold.py`** — after your first real ingest, run
   this to see the score distribution and pick `ALIGNMENT_THRESHOLD`.

## Operations

| Endpoint | Purpose |
|----------|---------|
| `GET /jobs?status=&min_score=` | Ranked queue |
| `PATCH /jobs/{id}/status` | applied / interviewing / rejected |
| `POST /jobs/{id}/deep-dive` → `GET /jobs/{id}/dossier` | AI dossier (async + poll) |
| `POST /ingest/run?provider=` | Manual ingest (all or one source) |
| `POST /freshness/run?worker=expiry\|heartbeat\|purge` | Manual freshness pass |
| `POST /profile/refresh` · `POST /filters/reload` | Hot-reload config |
| `GET /metrics` | Prometheus scrape target |

Full interactive API docs at `http://localhost:8000/docs`.

## Observability

- **Grafana** `http://localhost:3001` (admin/synapse) — auto-provisioned
  "SYNAPSE Operations" dashboard: API latency, ingest outcomes, jobs
  created, freshness activity, dossier durations.
- **Prometheus** `http://localhost:9090` — raw metrics.
- **Phoenix** `http://localhost:6006` — per-agent traces of every deep dive,
  including token-level LLM calls.

## Testing

```
cd backend  && pytest -v          # ~48 tests; DB/Chroma tests auto-skip if containers are down
cd frontend && npm test           # 9 component + markdown-stress tests
python scripts/e2e_smoke.py       # full-stack: insert → deep dive → verified report
python scripts/benchmark_ollama.py    # hardware gate (P0)
```

CI (GitHub Actions) runs both suites with real Postgres/Chroma service
containers on every push.

## Stack

FastAPI · SQLAlchemy 2 (async) · Alembic · PostgreSQL 16 · ChromaDB ·
sentence-transformers (all-MiniLM-L6-v2) · CrewAI · Ollama (Llama 3 8B) ·
APScheduler · Next.js 16 · React 19 · Tailwind CSS · Prometheus · Grafana ·
Arize Phoenix

## License

Proprietary — see `LICENSE`. Built as a licensable boilerplate; contact the
copyright holder for terms.
