# Project SYNAPSE

**Systematic Yield Network for AI Placement & Strategic Employment** — a privacy-first, zero-API-cost job intelligence system. See `project_blueprint.md` (PRD) and `PROJECT_PLAN.md` (build roadmap).

## Layout

```
backend/    FastAPI + SQLAlchemy + CrewAI (Python 3.11+)
frontend/   Next.js + Tailwind cyberpunk dashboard
scripts/    Phase 0 hardware benchmarks
docker-compose.yml   PostgreSQL 16 + ChromaDB
```

## Quick Start

```bash
# 1. Environment
cp .env.example .env        # fill in API keys as they arrive

# 2. Databases
docker compose up -d        # postgres :5432, chroma :8001

# 3. Backend
cd backend
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload                     # http://localhost:8000/health
pytest                                            # run tests

# 4. Frontend
cd frontend
npm install
npm run dev                                       # http://localhost:3000
```

## Phase 0 Hardware Gate

Before Phase 6 (AI agents) is committed to, run on this machine:

```bash
# Requires Ollama installed: https://ollama.com/download
ollama pull llama3:8b
ollama pull mistral:7b
python scripts/benchmark_ollama.py     # pass: >= 10 tok/s sustained

pip install sentence-transformers
python scripts/benchmark_embeddings.py # pass: 100 embeds < 30s
```

Results are written to `benchmark_results.json`.
