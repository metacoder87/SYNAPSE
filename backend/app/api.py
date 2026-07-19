"""REST API for the dashboard (P4.2 + P6.5 endpoints)."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app import artifacts as artifacts_module
from app import dossiers, repository
from app.config import settings
from app.db import get_session
from app.models.job import Job, JobStatus

router = APIRouter()

# Keep references so long-running deep-dive tasks aren't garbage-collected
_background_tasks: set[asyncio.Task] = set()


@router.get("/export/jobs.csv")
async def export_jobs_csv(session: AsyncSession = Depends(get_session)) -> Response:
    """F9: full pipeline as CSV."""
    import csv
    import io

    from sqlalchemy import select

    from app.models.orm import JobRow

    rows = (await session.execute(select(JobRow).order_by(JobRow.first_seen_at))).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "title", "company", "status", "alignment_score", "salary_min", "salary_max",
        "location", "remote", "security_clearance", "source", "posted_at",
        "closing_date", "first_seen_at", "job_url",
    ])
    for j in rows:
        writer.writerow([
            j.title, j.company, j.system_status.value,
            float(j.alignment_score) if j.alignment_score is not None else "",
            j.salary_min or "", j.salary_max or "", j.location_string or "",
            j.is_remote, j.security_clearance or "", j.source_provider,
            j.posted_at.isoformat() if j.posted_at else "",
            j.closing_date.isoformat() if j.closing_date else "",
            j.first_seen_at.isoformat() if j.first_seen_at else "",
            j.job_url,
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=synapse_jobs.csv"},
    )


@router.get("/export/backup.json")
async def export_backup(session: AsyncSession = Depends(get_session)) -> Response:
    """F9: full JSON backup — jobs, timeline, dossiers, artifacts."""
    import json

    from sqlalchemy import select

    from app.models.orm import ArtifactRow, DossierRow, JobRow, StatusEventRow

    def dump(rows):
        return [
            {c.name: getattr(r, c.name) for c in r.__table__.columns}
            for r in rows
        ]

    payload = {
        "exported_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "jobs": dump((await session.execute(select(JobRow))).scalars().all()),
        "status_events": dump((await session.execute(select(StatusEventRow))).scalars().all()),
        "dossiers": dump((await session.execute(select(DossierRow))).scalars().all()),
        "artifacts": dump((await session.execute(select(ArtifactRow))).scalars().all()),
    }
    return Response(
        content=json.dumps(payload, default=str, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=synapse_backup.json"},
    )


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
    note: str | None = None


class NoteBody(BaseModel):
    note: str


@router.patch("/jobs/{job_id}/status")
async def update_status(
    job_id: uuid.UUID,
    body: StatusUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    ok = await repository.set_status(session, job_id, body.status, note=body.note)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found")
    return {"id": str(job_id), "status": body.status.value}


@router.post("/jobs/{job_id}/notes")
async def add_note(
    job_id: uuid.UUID, body: NoteBody, session: AsyncSession = Depends(get_session)
) -> dict:
    ok = await repository.add_note(session, job_id, body.note)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found")
    return {"id": str(job_id), "noted": True}


@router.get("/jobs/{job_id}/events")
async def get_events(
    job_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    events = await repository.list_events(session, job_id)
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "status": e.status.value if e.status else None,
            "note": e.note,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/jobs/{job_id}/explain")
async def explain_job_score(
    job_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    """U1: which profile phrases drive this job's Alignment Score."""
    job = await repository.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    from app import matching

    matches = await asyncio.to_thread(
        matching.explain_score, job.title, job.description_markdown
    )
    return {"alignment_score": job.alignment_score, "top_matches": matches}


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


@router.post("/jobs/{job_id}/artifacts/{kind}")
async def start_artifact(
    job_id: uuid.UUID, kind: str, session: AsyncSession = Depends(get_session)
) -> dict:
    """Phase 12: generate a tailor pack or interview prep asynchronously."""
    if kind not in artifacts_module.KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {artifacts_module.KINDS}")
    job = await repository.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    existing = await artifacts_module.latest(session, job_id, kind)
    if existing is not None and existing.status == "running":
        return {"artifact_id": str(existing.id), "kind": kind, "status": "running",
                "note": "already in progress"}

    artifact_id = await artifacts_module.create(session, job_id, kind)
    task = asyncio.create_task(
        artifacts_module.run_generation_task(artifact_id, kind, job)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"artifact_id": str(artifact_id), "kind": kind, "status": "running"}


@router.get("/jobs/{job_id}/artifacts")
async def get_artifacts(
    job_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    rows = await artifacts_module.latest_all(session, job_id)
    return {
        kind: {
            "artifact_id": str(row.id),
            "status": row.status,
            "content_markdown": row.content_markdown,
            "error": row.error,
            "created_at": row.created_at.isoformat(),
        }
        for kind, row in rows.items()
    }


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
        "progress": row.progress,
        # Phase 10: verifiable research
        "evidence": row.evidence,
        "verdicts": row.verdicts,
        "prompt_version": row.prompt_version,
        "citation_coverage": float(row.citation_coverage) if row.citation_coverage is not None else None,
        "verified_ratio": float(row.verified_ratio) if row.verified_ratio is not None else None,
    }
