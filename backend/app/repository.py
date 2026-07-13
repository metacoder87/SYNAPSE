"""Repository layer — all database access for jobs goes through here (P1.4)."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.models.orm import JobRow

# Columns an adapter is allowed to refresh on re-ingest. Status and lifecycle
# fields are deliberately excluded so a re-scraped posting never clobbers
# a user's 'applied'/'interviewing' state.
_UPSERT_REFRESH_COLS = (
    "title",
    "company",
    "department",
    "location_string",
    "is_remote",
    "job_url",
    "apply_url",
    "salary_min",
    "salary_max",
    "salary_interval",
    "security_clearance",
    "description_markdown",
    "posted_at",
    "closing_date",
    "raw_metadata",
    "alignment_score",
)


async def upsert_job(session: AsyncSession, job: Job) -> tuple[uuid.UUID, bool]:
    """Insert a job, or refresh display fields if external_reference_id exists.

    Returns (job_id, created) where created=True for a new row.
    """
    values = job.model_dump(exclude={"id", "last_verified_at", "updated_at"}, exclude_none=False)
    values["system_status"] = job.system_status.value

    stmt = pg_insert(JobRow).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["external_reference_id"],
        set_={col: getattr(stmt.excluded, col) for col in _UPSERT_REFRESH_COLS},
    ).returning(JobRow.id, literal_column("(xmax = 0)").label("created"))

    result = await session.execute(stmt)
    row = result.one()
    await session.commit()
    return row.id, bool(row.created)


async def get_job(session: AsyncSession, job_id: uuid.UUID) -> Job | None:
    row = await session.get(JobRow, job_id)
    return Job.model_validate(row) if row else None


async def get_active_jobs(session: AsyncSession, limit: int = 100, offset: int = 0) -> list[Job]:
    stmt = (
        select(JobRow)
        .where(JobRow.system_status == JobStatus.ACTIVE)
        .order_by(JobRow.alignment_score.desc().nulls_last(), JobRow.posted_at.desc().nulls_last())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [Job.model_validate(r) for r in rows]


async def set_status(session: AsyncSession, job_id: uuid.UUID, status: JobStatus) -> bool:
    stmt = (
        update(JobRow)
        .where(JobRow.id == job_id)
        .values(system_status=status)
        .returning(JobRow.id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one_or_none() is not None


async def expire_past_closing(session: AsyncSession) -> int:
    """PRD §5 deterministic expiry: mark active jobs past their closing_date."""
    stmt = (
        update(JobRow)
        .where(
            JobRow.system_status == JobStatus.ACTIVE,
            JobRow.closing_date.is_not(None),
            JobRow.closing_date < datetime.now(timezone.utc),
        )
        .values(system_status=JobStatus.EXPIRED)
        .returning(JobRow.id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return len(result.scalars().all())


async def purge_expired(session: AsyncSession, older_than_days: int = 14) -> list[uuid.UUID]:
    """PRD §5 weekly purge: delete expired jobs stale for `older_than_days`.

    Returns deleted IDs so the caller can remove matching ChromaDB vectors.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    stmt = (
        delete(JobRow)
        .where(JobRow.system_status == JobStatus.EXPIRED, JobRow.updated_at < cutoff)
        .returning(JobRow.id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return list(result.scalars().all())


async def list_jobs(
    session: AsyncSession,
    status: JobStatus | None = None,
    min_score: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Job]:
    """Filterable job queue, sorted by Alignment Score (P4.2)."""
    stmt = select(JobRow)
    if status is not None:
        stmt = stmt.where(JobRow.system_status == status)
    if min_score is not None:
        stmt = stmt.where(JobRow.alignment_score >= min_score)
    stmt = (
        stmt.order_by(
            JobRow.alignment_score.desc().nulls_last(),
            JobRow.posted_at.desc().nulls_last(),
        )
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [Job.model_validate(r) for r in rows]
