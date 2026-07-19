# SYNAPSE v2 — Deep-Research Accuracy & Product Improvement Plan

> **STATUS: Phase 10 complete** (R1 evidence pipeline, R2 structured claims + deterministic rendering, R4.1–4.2 eval harness; R2.2 note: networker sections are labeled *(inference)* and exempt from fact-checking by design; R1.4 note: the RAG index is in-memory per dive rather than an ephemeral Chroma collection — same behavior, less lifecycle management). **Phase 11 complete** (E1 startup sweep — full durable queue deferred; E2 live progress via progress column + existing polling rather than SSE; U1 why-this-score; U2 timeline + notes; U3 NEW badges via first_seen_at; U5 saved prefs; F4 ntfy digest). **Phase 12 complete** (F1 tailor agent + master_resume.md + deterministic keyword gap; F2 dossier-aware interview prep; R3.1 numeric-literal prechecks; R3.5 OLLAMA_VERIFIER_MODEL; R4.3 Grafana quality panels; artifacts table 0006 with startup sweep). Remaining from Track R: R3.2 done in Phase 10 (temp-0 verifier), R3.3 self-consistency and R3.4 few-shot refusals still open. **Phase 13 complete** (E6 bearer auth + token UI; E5 delivered as validated file-editor settings page with hot reload/re-embed — full config-in-DB not needed while files remain the template surface; F9 CSV + JSON backup exports; E4 delivered as `npm run gen:api` generation script). **F7 multi-profile deferred** — needs its own session (schema: profiles table + per-profile scores + UI switcher). Remaining open items: F7, R3.3/R3.4, E1-full queue, E2-SSE, E3, E7, E8, E9, F2-F3-F5-F6-F8, U4, U6, U7.

Follow-on roadmap to `PROJECT_PLAN.md` (v1.0.0 complete). Three tracks:
**R** (research accuracy), **E/U** (engineering & UX), **F** (new features).
Task IDs are referenceable like the v1 plan.

---

## Track R — Agentic Deep-Research Accuracy

### Where accuracy leaks today (honest assessment of v1)

1. **Thin evidence.** The Scout gets five search snippets fetched once by
   company name. Snippets are ~300 chars, un-cited, and name collisions
   ("Apex Systems" the staffing firm vs. "Apex" the fintech) can poison the
   entire dossier with the wrong company's facts.
2. **Prose-level verification.** The Fact-Checker rewrites prose and marks
   things *[unverified]* by judgment. Nothing forces every claim to be
   checked; an 8B model will confidently pass through plausible fabrications
   (funding rounds, headcounts, founding years are classic hallucinations).
3. **No citations.** The final dossier asserts facts without pointing at
   evidence, so the user can't audit anything without redoing the research.
4. **No measurement.** We have latency metrics but zero accuracy metrics — a
   prompt change could silently make dossiers worse.

### R1 — Evidence store: retrieve pages, not snippets (highest impact)

| ID | Task | AC |
|----|------|----|
| R1.0 | **Serper as primary retrieval** *(done — wired into `_web_context` with DDG fallback; knowledge-graph facts included)*. All R1 searches go through Serper's structured JSON; budget note: ~5 queries/dive → monitor usage against plan limits | Serper used when `SERPER_API_KEY` set; graceful DDG fallback |
| R1.1 | Multi-query retrieval: per dive, run 4–6 targeted searches (`"<company>" funding`, `"<company>" engineering blog`, `"<company>" glassdoor OR levels.fyi`, `"<company>" layoffs OR news`, company careers site) | ≥3 distinct domains retrieved per dive |
| R1.2 | Fetch top results and extract full text with the existing `enrich`/trafilatura module; store as evidence docs with stable IDs (`E1…En`), URL, retrieval date | Evidence persisted per dossier (new `evidence` JSONB column or table) |
| R1.3 | Company disambiguation gate: before accepting evidence, a cheap LLM check ("is this page about the company hiring for <title> at <location>? y/n") using the job posting as anchor; discard mismatches | Wrong-company evidence rate near zero on a name-collision test set |
| R1.4 | Chunk + embed evidence into an ephemeral Chroma collection per dive; agents query it (true RAG) instead of receiving one blob | Scout answers grounded in retrieved chunks; context stays under model window |

### R2 — Structured claims with enforced citations

| ID | Task | AC |
|----|------|----|
| R2.1 | Scout and Networker output JSON (Pydantic-validated): list of claims, each `{text, evidence_ids, section}`; retry-on-invalid-JSON loop | 100% of scout/networker output parses; claims without `evidence_ids` are auto-tagged `uncited` |
| R2.2 | Fact-Checker becomes a per-claim verifier: for each claim, retrieve its cited chunks and output `supported / contradicted / insufficient` + one-line rationale | Verdict table stored alongside the dossier |
| R2.3 | Render the final markdown *deterministically in Python* from verified claims (sections, ¹²³ citation superscripts, sources list, verdict appendix) — the LLM never gets a chance to drop citations | Every factual sentence in the dossier traces to a URL; contradicted claims shown struck-through or omitted per config |

### R3 — Verification hardening

| ID | Task | AC |
|----|------|----|
| R3.1 | Deterministic validators before LLM judgment: dates, dollar amounts, URLs, and proper nouns in claims must literally appear in cited evidence (regex/fuzzy match); fail → downgrade to `insufficient` | Numeric hallucinations caught without spending tokens |
| R3.2 | Verification runs at `temperature=0`; generation stays at 0.4 | Config split per task type |
| R3.3 | Self-consistency on the verifier: run each claim's verdict twice; disagreement → `insufficient` (cheap at 100+ tok/s) | Flaky verdicts eliminated from `supported` |
| R3.4 | Prompt hard-rule: "You know nothing about any company. Only the evidence exists." + few-shot examples of correct refusals | Spot-check shows no outside-knowledge leakage |
| R3.5 | Tiered models: keep Llama 3 8B for extraction/networking; add a stronger local verifier model (e.g. `qwen2.5:32b` or `llama3.1:70b-q4` — benchmark first with `scripts/benchmark_ollama.py`) selected via `OLLAMA_VERIFIER_MODEL` | Verifier model configurable; falls back to primary |

### R4 — Accuracy evaluation harness (make quality measurable)

| ID | Task | AC |
|----|------|----|
| R4.1 | Golden set: 8–10 companies with hand-verified facts (founded, HQ, size range, funding stage, remote policy) in `eval/golden.yaml` | Committed fixture |
| R4.2 | `scripts/eval_dossiers.py`: run dives against the golden set; score citation coverage (% claims cited), faithfulness (% cited claims actually supported by their source), contradiction rate vs. golden facts | One-command eval report |
| R4.3 | Metrics: `synapse_dossier_citation_coverage`, `synapse_dossier_verified_ratio` exported to Prometheus; Grafana panel | Quality visible over time |
| R4.4 | Treat prompts as versioned artifacts: `prompt_version` column on dossiers; eval before/after any prompt change | Regressions caught before they ship |

**Sequencing note:** R1 → R2 → R3 build on each other; R4 can start in
parallel and should exist *before* R3 tuning (you can't tune what you can't
measure).

---

## Track E — Engineering & Architecture

| ID | Improvement | Why |
|----|-------------|-----|
| E1 | **Durable dive queue.** Replace fire-and-forget `asyncio.create_task` with a DB-backed queue; on startup, sweep dossiers stuck in `running` → `failed` ("server restarted") | Today a backend restart orphans running dives forever |
| E2 | **Live progress via SSE.** CrewAI step callbacks write a `progress` field ("scout: retrieving", "verifying claim 4/12"); frontend switches from 4s polling to an EventSource stream | Real progress instead of a spinner; fewer requests |
| E3 | **Adapter circuit breaker.** After N consecutive failures, an adapter cools down and `GET /sources/health` reports per-source status + last success | One dead API stops burning the whole sync cycle |
| E4 | **OpenAPI-generated TS client** (`openapi-typescript`) replacing hand-written `api.ts` types | Backend/Frontend contract can't drift |
| E5 | **Config in DB + settings UI.** Move filter rules, profile, keywords into Postgres with a `/settings` page (file mounts stay as seed/export) | Removes the last reason to touch files; required for any multi-user future |
| E6 | **Auth token.** Single shared bearer token (env) enforced by middleware, frontend attaches it | Prerequisite for exposing beyond localhost / LAN use |
| E7 | **Backups.** Nightly `pg_dump` to a mounted folder + Chroma volume snapshot script | The application history is becoming valuable personal data |
| E8 | **Structured JSON logging + correlation IDs** across ingest → score → persist → dive | Greppable causality; feeds Grafana Loki later |
| E9 | **Alembic drift check in CI** (`alembic check` / autogenerate diff must be empty) | Schema and ORM can't diverge silently |

## Track U — User Experience

| ID | Improvement | Why |
|----|-------------|-----|
| U1 | **"Why this score"** — store chunk-level similarity and show the top 3 matching profile phrases on the detail page | Trust in the ranking; guides profile tuning |
| U2 | **Status history timeline** (`status_events` table) — applied on date X, interview on Y, with notes field per job | It's an application tracker, not just a feed |
| U3 | **Seen/new tracking** — "NEW" badge since last visit; count on the tab | The daily-queue workflow the PRD promised |
| U4 | **Keyboard nav** — j/k move, Enter open, a=applied, r=rejected | Power-user speed for daily triage |
| U5 | **Saved view preferences** (localStorage): tab, sort, filters persist | Small friction, daily payoff |
| U6 | **Dossier UX** — sticky table of contents, citation hover-previews, export to PDF | Dossiers become shareable artifacts |
| U7 | **Mobile pass** — the queue is usable on a phone; deep dives readable | Triage from anywhere |
| U8 | **Empty/error states with next actions** everywhere (partially done) | Polish expected of a sellable product |

---

## Track F — Value-Add Features (backlog, roughly by value/effort)

| ID | Feature | Value proposition |
|----|---------|-------------------|
| F1 | **Resume & cover-letter tailor agent** — new crew: takes your master resume + the job description, outputs tailored bullets, a cover letter draft, and a keyword-gap report. Runs fully local — privacy is the moat here | Turns SYNAPSE from "finds jobs" into "helps win jobs"; biggest single value-add |
| F2 | **Interview prep pack** — from a completed dossier: likely interview questions, STAR answer skeletons mapped to your profile, questions to ask them | Natural chain after DEEP DIVE; reuses evidence store |
| F3 | **Feedback-loop re-ranking** — thumbs up/down on jobs trains a lightweight re-ranker (logistic regression over embeddings) blended with cosine score | The queue gets smarter every day you use it; strong demo story for buyers |
| F4 | **Daily digest notifications** — new above-threshold jobs pushed via ntfy/email (local SMTP); closing-date reminders for applied roles | Brings you back to the queue; deadlines never slip |
| F5 | **Company watchlist** — track target companies; alert on any new posting (Greenhouse/Lever slugs already supported) | Proactive targeting instead of reactive filtering |
| F6 | **Salary intelligence** — percentile of each posting against your ingested corpus; salary distribution chart by title/remote | Negotiation leverage from data you already have |
| F7 | **Multi-profile support** — N profiles (e.g., "AI Architect" + "Staff MLE"), per-profile scores and queues | Doubles as multi-tenant groundwork for the boilerplate sale |
| F8 | **Outreach CRM-lite** — contacts per company, outreach drafts (Networker agent already suggests angles), follow-up reminders | Closes the loop on the Networker's output |
| F9 | **Export pack** — CSV of pipeline, PDF dossiers, JSON full backup | Data portability; buyer checklist item |

---

## Recommended sequencing

**Phase 10 (accuracy core):** R1 → R2 → R4.1–R4.2 — evidence store,
enforced citations, and the eval harness. This is the difference between a
demo and a trustworthy tool, and it's a prerequisite for F1/F2.

**Phase 11 (daily-driver UX):** E1, E2, U1, U2, U3, U5 + F4 — durable dives,
live progress, tracker workflow, notifications. Makes SYNAPSE the thing you
open every morning.

**Phase 12 (win-jobs features):** F1, F2, then R3.5 verifier upgrade and
R4.3–R4.4. The tailor agent is the headline feature of the sellable product.

**Phase 13 (productization II):** E4, E5, E6, F7, F9 — settings UI, auth,
multi-profile, export. This is the boilerplate-buyer feature set.

Defer freely: E3/E7/E8/E9 slot in anywhere; F3/F5/F6/F8 by appetite.

## Effort guide

Rough, at your demonstrated pace (hardware is not a constraint at 104 tok/s):
Phase 10 ≈ 4–6 sessions · Phase 11 ≈ 3–4 · Phase 12 ≈ 4–5 · Phase 13 ≈ 3–4.
