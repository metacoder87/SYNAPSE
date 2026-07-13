"""Dossier persistence + async deep-dive orchestration (P6.5)."""

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
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _finish(dossier_id: uuid.UUID, *, status: str,
                  content: str | None = None, error: str | None = None) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(DossierRow)
            .where(DossierRow.id == dossier_id)
            .values(
                status=status,
                content_markdown=content,
                error=error,
                completed_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def run_deep_dive_task(dossier_id: uuid.UUID, job: Job) -> None:
    """Background task: run the CrewAI pipeline in a worker thread and persist."""
    from app.agents.crew import run_deep_dive  # deferred heavy import

    start = time.perf_counter()
    try:
        markdown = await asyncio.to_thread(
            run_deep_dive, job.title, job.company, job.description_markdown
        )
        await _finish(dossier_id, status="complete", content=markdown)
        metrics.record_dossier("complete", time.perf_counter() - start)
        logger.info("dossier %s complete (%d chars)", dossier_id, len(markdown))
    except Exception as exc:  # noqa: BLE001
        metrics.record_dossier("failed", time.perf_counter() - start)
        logger.error("dossier %s failed: %s", dossier_id, str(exc)[:300])
        await _finish(dossier_id, status="failed", error=str(exc)[:1000])
