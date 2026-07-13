"""P8.3 — End-to-end smoke test (PRD §8 Integration).

Verifies: dummy Postgres insertion → CrewAI deep-dive trigger → formatted
report within an acceptable local-compute time budget.

Run ON YOUR MACHINE with the full stack up (docker compose, uvicorn, Ollama):
    python scripts/e2e_smoke.py
"""

import asyncio
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

API = "http://localhost:8000"
TIME_BUDGET_SECONDS = 600  # generous for local generation; tune per hardware
POLL_SECONDS = 5

DUMMY = {
    "title": "E2E Smoke Test — Corporate AI Architect",
    "company": "NeoGrid Systems (E2E)",
    "description": (
        "# Corporate AI Architect\n\nNeoGrid Systems seeks a Corporate AI "
        "Architect to own enterprise AI strategy: multi-agent orchestration, "
        "RAG platforms, vector databases, and LLMOps. 100% remote (US). "
        "Salary $190k–$240k.\n\n## Requirements\n- 10y systems design\n- LLM "
        "platform experience\n"
    ),
}


async def main() -> int:
    from sqlalchemy import text

    from app.db import SessionLocal
    from app.models.job import Job
    from app import repository

    print("1/4 Inserting dummy job into Postgres...")
    job = Job(
        source_provider="e2e",
        external_reference_id=f"e2e:{int(time.time())}",
        title=DUMMY["title"],
        company=DUMMY["company"],
        job_url="https://example.com/e2e",
        description_markdown=DUMMY["description"],
        is_remote=True,
    )
    async with SessionLocal() as session:
        job_id, _ = await repository.upsert_job(session, job)
    print(f"    job_id = {job_id}")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            print("2/4 Triggering deep-dive endpoint...")
            r = await client.post(f"{API}/jobs/{job_id}/deep-dive")
            r.raise_for_status()
            print(f"    {r.json()}")

            print(f"3/4 Polling dossier (budget: {TIME_BUDGET_SECONDS}s)...")
            start = time.perf_counter()
            while True:
                elapsed = time.perf_counter() - start
                if elapsed > TIME_BUDGET_SECONDS:
                    print(f"FAIL: exceeded {TIME_BUDGET_SECONDS}s budget")
                    return 1
                d = (await client.get(f"{API}/jobs/{job_id}/dossier")).json()
                if d["status"] == "complete":
                    break
                if d["status"] == "failed":
                    print(f"FAIL: dossier failed — {d['error']}")
                    return 1
                print(f"    running... {elapsed:.0f}s", flush=True)
                await asyncio.sleep(POLL_SECONDS)

        md = d["content_markdown"] or ""
        checks = {
            "non-empty report": len(md) > 200,
            "has markdown headers": "#" in md,
            "within time budget": elapsed <= TIME_BUDGET_SECONDS,
        }
        print(f"4/4 Report received in {elapsed:.0f}s ({len(md)} chars)")
        for name, ok in checks.items():
            print(f"    {'PASS' if ok else 'FAIL'}: {name}")
        return 0 if all(checks.values()) else 1

    finally:
        async with SessionLocal() as session:
            await session.execute(
                text("DELETE FROM jobs WHERE source_provider = 'e2e'")
            )
            await session.commit()
        print("    (e2e rows cleaned up)")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
