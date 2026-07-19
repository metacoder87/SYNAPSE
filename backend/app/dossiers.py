"""Dossier persistence + async deep-dive orchestration (P6.5, Phase 10)."""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import metrics
from app.db import SessionLocal
from app.models.job import Job
from app.models.orm import DossierRow

logger = logging.getLogger("synapse.dossiers")


async def _set_progress(dossier_id: uuid.UUID, stage: str) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(DossierRow).where(DossierRow.id == dossier_id).values(progress=stage[:120])
        )
        await session.commit()


async def sweep_stale_running() -> int:
    """E1: on startup, fail dossiers orphaned by a previous shutdown.

    Fail-soft: returns 0 if the DB isn't reachable yet."""
    try:
        return await _sweep()
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup sweep skipped: %s", str(exc)[:150])
        return 0


async def _sweep() -> int:
    async with SessionLocal() as session:
        result = await session.execute(
            update(DossierRow)
            .where(DossierRow.status == "running")
            .values(
                status="failed",
                error="server restarted before completion",
                completed_at=datetime.now(timezone.utc),
            )
            .returning(DossierRow.id)
        )
        swept = len(result.scalars().all())
        await session.commit()
    if swept:
        logger.warning("startup sweep: %d orphaned running dossier(s) marked failed", swept)
    return swept


async def create_dossier(session: AsyncSession, job_id: uuid.UUID) -> uuid.UUID:
    row = DossierRow(job_id=job_id, status="running")
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row.id


async def latest_for_job(session: AsyncSession, job_id: uuid.UUID) -> DossierRow | None:
    stmt = (
        select(DossierRow)
        .where(DossierRow.job_id == job_id)
        .order_by(DossierRow.created_at.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _finish(dossier_id: uuid.UUID, *, status: str, error: str | None = None,
                  result=None) -> None:
    values: dict = {
        "status": status,
        "error": error,
        "completed_at": datetime.now(timezone.utc),
    }
    if result is not None:
        values.update(
            content_markdown=result.markdown,
            evidence=result.evidence,
            verdicts=result.verdicts,
            prompt_version=result.prompt_version,
            citation_coverage=result.citation_coverage,
            verified_ratio=result.verified_ratio,
        )
    async with SessionLocal() as session:
        await session.execute(
            update(DossierRow).where(DossierRow.id == dossier_id).values(**values)
        )
        await session.commit()


async def run_deep_dive_task(dossier_id: uuid.UUID, job: Job) -> None:
    """Background task: run the research pipeline in a worker thread and persist."""
    from app.agents.crew import run_deep_dive  # deferred heavy import

    loop = asyncio.get_running_loop()

    def progress_cb(stage: str) -> None:
        # called from the worker thread — hop back onto the event loop
        asyncio.run_coroutine_threadsafe(_set_progress(dossier_id, stage), loop)

    start = time.perf_counter()
    try:
        result = await asyncio.to_thread(
            run_deep_dive, job.title, job.company, job.description_markdown, progress_cb
        )
        await _finish(dossier_id, status="complete", result=result)
        metrics.record_dossier("complete", time.perf_counter() - start)
        metrics.record_dossier_quality(result.citation_coverage, result.verified_ratio)
        logger.info(
            "dossier %s complete (%d chars, %d sources, coverage=%.2f, verified=%.2f)",
            dossier_id, len(result.markdown), len(result.evidence),
            result.citation_coverage, result.verified_ratio,
        )
    except Exception as exc:  # noqa: BLE001
        metrics.record_dossier("failed", time.perf_counter() - start)
        logger.error("dossier %s failed: %s", dossier_id, str(exc)[:300])
        await _finish(dossier_id, status="failed", error=str(exc)[:1000])


# Alias used by app.main
sweep_orphaned = sweep_stale_running
