"""P3.5 — Alignment Score threshold calibration.

Run ON YOUR MACHINE from the repo root (needs DB up + backend venv active):
    python scripts/calibrate_threshold.py

Scores extreme dummy texts plus every job currently in Postgres against the
candidate profile, prints the distribution, and suggests a threshold.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

PERFECT_MATCH = """Corporate AI Architect — 100% remote (US). Own enterprise AI
strategy and macro-level architecture: multi-agent orchestration, RAG and
vector database design, local-first LLM deployment with Ollama, LLMOps
observability. Principal/Director scope advising executive leadership."""

TOTAL_MISMATCH = """Seasonal lifeguard needed for community pool. Must be able
to swim 500 yards, maintain pool chemistry logs, and supervise children.
Weekend availability required. No remote work possible, obviously."""

ADJACENT_ROLE = """Senior Machine Learning Engineer. Hands-on model training,
feature pipelines, and deploying PyTorch models to production. Hybrid, 3 days
in our NYC office."""


async def main() -> None:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.matching import score_job_text
    from app.models.orm import JobRow

    print("=== Extreme dummy data (P3.5 sanity anchors) ===")
    anchors = [
        ("PERFECT MATCH ", PERFECT_MATCH),
        ("ADJACENT ROLE ", ADJACENT_ROLE),
        ("TOTAL MISMATCH", TOTAL_MISMATCH),
    ]
    for label, text_ in anchors:
        score, _ = score_job_text(label.strip(), text_)
        print(f"  {label}: {score}")

    print("\n=== Real ingested jobs ===")
    async with SessionLocal() as session:
        rows = (await session.execute(select(JobRow).limit(500))).scalars().all()

    if not rows:
        print("  (no jobs in DB — run an ingest first)")
        return

    scored = []
    for row in rows:
        score, _ = score_job_text(row.title, row.description_markdown)
        scored.append((score, row.title[:60], row.source_provider))

    scored.sort(reverse=True, key=lambda x: x[0] or 0)

    print(f"\n  Top 10 of {len(scored)}:")
    for score, title, provider in scored[:10]:
        print(f"    {score:.4f}  [{provider}] {title}")
    print("\n  Bottom 5:")
    for score, title, provider in scored[-5:]:
        print(f"    {score:.4f}  [{provider}] {title}")

    values = [s for s, _, _ in scored if s is not None]
    print("\n=== Distribution ===")
    for lo in (x / 10 for x in range(0, 10)):
        n = sum(1 for v in values if lo <= v < lo + 0.1)
        print(f"  {lo:.1f}–{lo + 0.1:.1f}: {'#' * n} ({n})")

    values.sort(reverse=True)
    p75 = values[int(len(values) * 0.25)] if values else 0
    print(f"\nSuggested starting threshold (75th percentile): {p75:.2f}")
    print("Set ALIGNMENT_THRESHOLD in .env once you've eyeballed the ranking above.")


if __name__ == "__main__":
    asyncio.run(main())
