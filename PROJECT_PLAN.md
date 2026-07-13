# Project SYNAPSE — Build Plan

Task-level roadmap following the blueprint (PRD) section order. Each phase lists tasks with acceptance criteria (AC). Databases run in Docker; Phase 0 verifies local AI hardware before anything is built around it.

**Legend:** ☐ pending · Each task ID (e.g., `P2.3`) can be referenced when we start work.

---

## Phase 0 — Environment & Hardware Verification (Gate)

Nothing in Phases 4+ is worth building if the local LLM can't run acceptably. This phase is a go/no-go gate.

| ID | Task | AC |
|----|------|----|
| P0.1 | Install Ollama; pull `llama3:8b` and `mistral:7b` | `ollama run llama3:8b` responds |
| P0.2 | Benchmark generation: time a ~500-token markdown generation on each model; record tokens/sec and RAM/VRAM usage | ≥10 tok/s sustained without swapping; pick primary model. If <10 tok/s, decide fallback (quantized variant, smaller model, or revisit scope) |
| P0.3 | Verify embedding model: run `all-MiniLM-L6-v2` via `sentence-transformers`, embed 100 sample texts | Batch of 100 embeds in <30s CPU |
| P0.4 | Create `docker-compose.yml` with PostgreSQL 16 + ChromaDB services, named volumes, healthchecks | `docker compose up` → both healthy; connect from host with psql and chroma client |
| P0.5 | Scaffold monorepo: `backend/` (FastAPI, uv/poetry, pytest), `frontend/` (Next.js + Tailwind + TypeScript), `.env.example`, README, git init | Backend serves `/health`; frontend renders default page; both lint clean |

**Exit criteria:** LLM benchmark passes, containers run, both apps boot.

---

## Phase 1 — Core Data Model & Database Layer (PRD §4)

| ID | Task | AC |
|----|------|----|
| P1.1 | Write initial migration (Alembic) implementing the `jobs` table + `job_status` enum from the PRD; add `updated_at` column with trigger (referenced by purge logic in §5 but missing from schema) | Migration up/down clean; schema matches PRD + `updated_at` |
| P1.2 | Add indexes: `system_status`, `closing_date`, plus `(source_provider, external_reference_id)` unique constraint behavior verified | Duplicate external ID insert fails gracefully |
| P1.3 | Define the unified `Job` Pydantic model mirroring the table, with validators (salary sanity, URL format, timezone-aware datetimes) | Round-trips DB row ↔ model; invalid payloads rejected with clear errors |
| P1.4 | Repository layer: `upsert_job`, `get_active_jobs`, `set_status`, `purge_expired` (dedupe on `external_reference_id`) | Unit tests pass against a Dockerized test DB |
| P1.5 | ChromaDB collection setup: `jobs` collection keyed by Postgres UUID, plus a `candidate_profile` document | Insert/query smoke test passes |

---

## Phase 2 — Data Ingestion & Adapter Pattern (PRD §3)

Build the adapter framework first, then one adapter end-to-end, then the rest.

| ID | Task | AC |
|----|------|----|
| P2.1 | Define `SourceAdapter` abstract base: `fetch() -> list[RawPayload]`, `parse(raw) -> Job`; shared rate-limit/retry/backoff wrapper (handles 429s) | Framework unit-tested with a mock adapter |
| P2.2 | **USAJobs adapter** (first, highest priority): auth key setup, extract clearance from `UserArea.Details.JobSummary`, map `closing_date`; overflow → `raw_metadata` | Real API call returns ≥1 parsed `Job` persisted to Postgres |
| P2.3 | Adzuna adapter + Jooble adapter with strict query params (title keywords, remote flag, US) | Parsed jobs persisted; params configurable via `.env` |
| P2.4 | Greenhouse & Lever JSON adapters driven by a configurable company allowlist | Add a company slug → its postings ingest |
| P2.5 | RSS adapters (WeWorkRemotely, RemoteOK): XML parse, isolate `<description>`, HTML→markdown conversion | Feed items become valid `Job` rows with clean `description_markdown` |
| P2.6 | Scheduler: APScheduler jobs per source with configurable intervals; structured logging of run outcomes (fetched/parsed/upserted/failed counts) | Scheduler runs all adapters on boot + interval; logs visible |

**Note:** Register for API keys (USAJobs, Adzuna, Jooble) early — approval can take days. Do this during Phase 0/1.

---

## Phase 3 — Filtering & Matching Engine (PRD §6 core engine)

| ID | Task | AC |
|----|------|----|
| P3.1 | Regex Kill Switch: configurable include/exclude keyword rules (e.g., must-match architect/AI terms; exclude junior/onsite-only); discarded jobs logged with reason, not persisted | Rule file editable without code change; mock payload tests pass |
| P3.2 | Candidate profile document: write the primary profile (target role, skills, constraints: remote/relocation, US) and embed it into ChromaDB | Profile embedding stored and retrievable |
| P3.3 | Embedding pipeline: on ingest pass, embed `description_markdown`, store vector in Chroma keyed to job UUID | New jobs get vectors automatically |
| P3.4 | Alignment Score: cosine similarity vs. candidate profile; persist score; threshold gate (start at 0.85 per PRD, but make configurable — validate empirically in P3.5) | Score stored per job; below-threshold jobs marked, not surfaced |
| P3.5 | Calibrate threshold with extreme dummy data (perfect match, total mismatch) + a sample of real ingested jobs | Documented score distribution; chosen threshold justified |

---

## Phase 4 — Frontend Dashboard (PRD §2 frontend, §6 UI)

| ID | Task | AC |
|----|------|----|
| P4.1 | Tailwind theme: `#0a0a0a` bg, cyan `#06b6d4` / magenta `#db2777` glow borders (box-shadow utilities), Space Mono font; base layout shell | Theme tokens centralized; renders per spec |
| P4.2 | FastAPI read endpoints: `GET /jobs` (sorted by alignment score, filterable by status), `GET /jobs/{id}` | OpenAPI docs correct; CORS configured for Next.js |
| P4.3 | Job queue view: card list with title/company/score/salary/clearance/deadline badges, status filter tabs | Live data renders; empty/loading states styled |
| P4.4 | Job detail view: `react-markdown` rendering of `description_markdown` with link/table support; status actions (applied / rejected) wired to `PATCH /jobs/{id}/status` | Heavy markdown (tables, long links) doesn't break grid |
| P4.5 | "Deep Dive" button (UI + placeholder endpoint returning stubbed report) — real agent wiring in Phase 6 | Button triggers request, renders stub markdown dossier |

---

## Phase 5 — Data Freshness / Stale Job Purge (PRD §5)

| ID | Task | AC |
|----|------|----|
| P5.1 | Deterministic expiry cron: daily job sets `expired` where `closing_date < now()` | Unit test with backdated rows |
| P5.2 | Async heartbeat worker (12h): HEAD/GET active job URLs; detect 404s, generic-board redirects, "position has been filled" text; concurrency-limited with per-domain politeness delay | Mocked-HTTP tests cover all three detection paths |
| P5.3 | Weekly purge: delete `expired` rows with `updated_at` > 14 days old; delete matching Chroma vectors in same transaction flow | Postgres and Chroma stay consistent after purge |

---

## Phase 6 — AI Agent Layer (PRD §2 AI stack, §6 Local AI Hive)

| ID | Task | AC |
|----|------|----|
| P6.1 | Ollama integration module: LLM client config for CrewAI pointing at local server, model selected in P0.2 | CrewAI completes a trivial single-agent task locally |
| P6.2 | Company Scout agent: researches company (size, funding, AI maturity, remote policy) from job description + web search tooling | Produces structured markdown section with sources |
| P6.3 | Networker agent: identifies likely hiring manager/team signals, suggests outreach angles | Markdown section with actionable items |
| P6.4 | Fact-Checker agent: verifies claims from the other two agents against source text; strips or flags unverifiable claims | Report marks verified vs. unverified claims |
| P6.5 | Crew orchestration: `POST /jobs/{id}/deep-dive` runs Scout → Networker → Fact-Checker, returns final markdown dossier; persist dossier; run async with progress polling (local generation is slow) | End-to-end dossier for a real job in acceptable time; UI shows progress state |
| P6.6 | Replace P4.5 stub with real endpoint | Dashboard renders real dossier with working hyperlinks |

---

## Phase 7 — Observability & LLMOps (PRD §7)

| ID | Task | AC |
|----|------|----|
| P7.1 | Prometheus + Grafana in docker-compose; FastAPI metrics middleware (latency, error rates); node/GPU exporter for hardware stats | Dashboard shows endpoint latency + resource usage |
| P7.2 | Cron/scheduler success-rate metrics (per-adapter success/failure counters) | Adapter failure visible in Grafana |
| P7.3 | Arize Phoenix tracing on CrewAI pipeline: agent thought traces, Chroma retrieval hit rates, tokens/sec | A deep-dive run produces a browsable trace |

---

## Phase 8 — Testing Suite Hardening (PRD §8)

Tests are written *within* each phase; this phase closes gaps and adds integration coverage.

| ID | Task | AC |
|----|------|----|
| P8.1 | Backend: kill-switch mock payload matrix; `pytest-httpx` 429/fault-tolerance tests; Chroma similarity assertions with extreme dummy data | All PRD §8 backend cases covered |
| P8.2 | Frontend: Jest + RTL for theme classes and `react-markdown` stress rendering | Passes per PRD §8 |
| P8.3 | E2E integration: script inserts dummy Postgres row → triggers deep-dive → asserts formatted report within time budget | Green run in local environment |
| P8.4 | CI: GitHub Actions running backend + frontend suites on push (LLM-dependent tests mocked) | CI green |

---

## Phase 9 — Productization Prep (PRD §1 monetization)

Deferred until the system is matching well. Minimal now: keep it packageable.

- Config-over-code discipline throughout (profiles, keywords, thresholds, sources in config files/.env).
- One-command bootstrap (`docker compose up` + seed script).
- Later: docs, license, strip personal profile data, template repo.

---

## Dependency Graph

```
P0 (gate) → P1 → P2 → P3 → P4 ─┐
                    │           ├→ P6 → P7 → P8 (final pass) → P9
                    └→ P5 ──────┘
```

P5 (purge) can run in parallel with P4. P7 can start earlier if debugging demands it.

## Key Risks & Decisions to Watch

1. **Local LLM throughput (P0.2)** — the whole agent layer depends on it. Gate hard.
2. **0.85 cosine threshold** — likely too strict for MiniLM in practice; treat as tunable (P3.5), not fixed.
3. **API key lead times** — USAJobs/Adzuna/Jooble registration should start immediately.
4. **Heartbeat worker etiquette** — respect robots/rate limits to avoid IP blocks that would poison freshness data.
5. **Schema gap** — PRD §5 references `updated_at`, absent from §4 schema; added in P1.1.
