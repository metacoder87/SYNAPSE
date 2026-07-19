"""Artifact persistence + async generation (Phase 12: tailor, interview)."""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.job import Job
from app.models.orm import ArtifactRow

logger = logging.getLogger("synapse.artifacts")

KINDS = ("tailor", "interview")


async def create(session: AsyncSession, job_id: uuid.UUID, kind: str) -> uuid.UUID:
    row = ArtifactRow(job_id=job_id, kind=kind, status="running")
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row.id


async def latest(session: AsyncSession, job_id: uuid.UUID, kind: str) -> ArtifactRow | None:
    stmt = (
        select(ArtifactRow)
        .where(ArtifactRow.job_id == job_id, ArtifactRow.kind == kind)
        .order_by(ArtifactRow.created_at.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def latest_all(session: AsyncSession, job_id: uuid.UUID) -> dict[str, ArtifactRow]:
    return {
        kind: row
        for kind in KINDS
        if (row := await latest(session, job_id, kind)) is not None
    }


async def _finish(artifact_id: uuid.UUID, *, status: str,
                  content: str | None = None, error: str | None = None) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(ArtifactRow)
            .where(ArtifactRow.id == artifact_id)
            .values(
                status=status,
                content_markdown=content,
                error=error,
                completed_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def sweep_orphaned() -> int:
    """E1 parity: fail artifacts orphaned by restarts (called at startup)."""
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                update(ArtifactRow)
                .where(ArtifactRow.status == "running")
                .values(
                    status="failed",
                    error="orphaned by server restart — generate again",
                    completed_at=datetime.now(timezone.utc),
                )
                .returning(ArtifactRow.id)
            )
            swept = len(result.scalars().all())
            await session.commit()
        if swept:
            logger.warning("startup sweep: %d orphaned artifact(s) marked failed", swept)
        return swept
    except Exception as exc:  # noqa: BLE001
        logger.warning("artifact sweep skipped: %s", str(exc)[:150])
        return 0


async def run_generation_task(artifact_id: uuid.UUID, kind: str, job: Job) -> None:
    start = time.perf_counter()
    try:
        if kind == "tailor":
            from app.agents.tailor import run_tailor

            markdown = await asyncio.to_thread(
                run_tailor, job.title, job.company, job.description_markdown
            )
        elif kind == "interview":
            from app.agents.interview import run_interview_prep
            from app.dossiers import latest_for_job

            async with SessionLocal() as session:
                dossier = await latest_for_job(session, job.id)
            dossier_md = (
                dossier.content_markdown
                if dossier is not None and dossier.status == "complete"
                else None
            )
            markdown = await asyncio.to_thread(
                run_interview_prep, job.title, job.company,
                job.description_markdown, dossier_md,
            )
        else:
            raise ValueError(f"unknown artifact kind: {kind}")

        await _finish(artifact_id, status="complete", content=markdown)
        logger.info("artifact %s (%s) complete in %.0fs (%d chars)",
                    artifact_id, kind, time.perf_counter() - start, len(markdown))
    except Exception as exc:  # noqa: BLE001
        logger.error("artifact %s (%s) failed: %s", artifact_id, kind, str(exc)[:300])
        await _finish(artifact_id, status="failed", error=str(exc)[:1000])
