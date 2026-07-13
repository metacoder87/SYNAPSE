"""REST API for the dashboard (P4.2 + P6.5 endpoints)."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app import dossiers, repository
from app.config import settings
from app.db import get_session
from app.models.job import Job, JobStatus

router = APIRouter()

# Keep references so long-running deep-dive tasks aren't garbage-collected
_background_tasks: set[asyncio.Task] = set()


@router.get("/config")
async def get_config() -> dict:
    return {
        "alignment_threshold": settings.alignment_threshold,
        "ollama_model": settings.ollama_model,
    }


@router.get("/jobs", response_model=list[Job])
async def get_jobs(
    status: JobStatus | None = JobStatus.ACTIVE,
    min_score: float | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[Job]:
    return await repository.list_jobs(
        session, status=status, min_score=min_score, limit=limit, offset=offset
    )


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Job:
    job = await repository.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


class StatusUpdate(BaseModel):
    status: JobStatus


@router.patch("/jobs/{job_id}/status")
async def update_status(
    job_id: uuid.UUID,
    body: StatusUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    ok = await repository.set_status(session, job_id, body.status)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found")
    return {"id": str(job_id), "status": body.status.value}


@router.post("/jobs/{job_id}/deep-dive")
async def start_deep_dive(
    job_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    """Kick off the CrewAI pipeline asynchronously (P6.5). Poll the dossier
    endpoint for progress — local generation takes a while."""
    job = await repository.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    existing = await dossiers.latest_for_job(session, job_id)
    if existing is not None and existing.status == "running":
        return {"dossier_id": str(existing.id), "status": "running", "note": "already in progress"}

    dossier_id = await dossiers.create_dossier(session, job_id)
    task = asyncio.create_task(dossiers.run_deep_dive_task(dossier_id, job))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"dossier_id": str(dossier_id), "status": "running"}


@router.get("/jobs/{job_id}/dossier")
async def get_dossier(
    job_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    row = await dossiers.latest_for_job(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="no dossier for this job")
    return {
        "dossier_id": str(row.id),
        "status": row.status,
        "content_markdown": row.content_markdown,
        "error": row.error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }
