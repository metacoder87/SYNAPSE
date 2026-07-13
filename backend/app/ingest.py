"""Ingestion pipeline (P2.6 + P3): adapter → Job → kill switch → score → persist.

Flow per job (PRD §6 Core Engine):
  parse → Regex Kill Switch → embed + Alignment Score → Postgres upsert
        → ChromaDB vector store (keyed by Postgres UUID)
"""

import logging
from dataclasses import asdict, dataclass

import httpx

from app.adapters import all_adapters, get_adapter
from app.adapters.base import SourceAdapter
from app.db import SessionLocal
from app.filtering import kill_switch
from app import matching, metrics, repository, vector

logger = logging.getLogger("synapse.ingest")


@dataclass
class IngestStats:
    provider: str
    fetched: int = 0
    parsed: int = 0
    parse_failed: int = 0
    filtered: int = 0
    created: int = 0
    refreshed: int = 0
    persist_failed: int = 0
    error: str | None = None


async def run_one(adapter: SourceAdapter) -> IngestStats:
    stats = IngestStats(provider=adapter.provider)
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            result = await adapter.run(client)
    except Exception as exc:  # noqa: BLE001
        stats.error = str(exc)[:300]
        logger.error("%s: fetch failed — %s", adapter.provider, stats.error)
        metrics.record_ingest(adapter.provider, 0, 0, error=True)
        return stats

    stats.fetched = result.fetched
    stats.parsed = result.parsed
    stats.parse_failed = result.failed

    async with SessionLocal() as session:
        for job in result.jobs:
            # --- Regex Kill Switch (P3.1): discard before spending compute
            passed, reason = kill_switch(job)
            if not passed:
                stats.filtered += 1
                logger.info("KILL [%s] %s — %s", adapter.provider, job.title[:60], reason)
                continue

            # --- Alignment Score (P3.3/P3.4)
            embedding: list[float] | None = None
            try:
                job.alignment_score, embedding = matching.score_job_text(
                    job.title, job.description_markdown
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("scoring failed for %s — %s (persisting unscored)",
                               job.external_reference_id, str(exc)[:200])

            # --- Persist to Postgres, then mirror vector to Chroma
            try:
                job_id, created = await repository.upsert_job(session, job)
                if created:
                    stats.created += 1
                else:
                    stats.refreshed += 1
            except Exception as exc:  # noqa: BLE001
                stats.persist_failed += 1
                logger.error("%s: persist failed for %s — %s",
                             adapter.provider, job.external_reference_id, str(exc)[:200])
                continue

            if embedding is not None:
                try:
                    vector.add_job_vector(
                        str(job_id),
                        embedding=embedding,
                        document=f"{job.title}\n\n{job.description_markdown}"[:8000],
                        metadata={
                            "source_provider": job.source_provider,
                            "title": job.title[:200],
                            "alignment_score": job.alignment_score or 0.0,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("vector store failed for %s — %s", job_id, str(exc)[:200])

    metrics.record_ingest(adapter.provider, stats.created, stats.filtered, error=False)
    logger.info("ingest %s: %s", adapter.provider, asdict(stats))
    return stats


async def run_all() -> list[IngestStats]:
    return [await run_one(adapter) for adapter in all_adapters()]


async def run_provider(provider: str) -> IngestStats | None:
    adapter = get_adapter(provider)
    return await run_one(adapter) if adapter else None
