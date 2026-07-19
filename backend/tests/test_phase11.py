"""Phase 11 — timeline events, startup sweep, digest query logic (needs DB)."""

from app import repository
from app.db import SessionLocal
from app.dossiers import create_dossier, latest_for_job, sweep_stale_running
from app.models.job import JobStatus
from tests.conftest import make_job, requires_db

pytestmark = requires_db


async def test_status_change_records_event(db_session):
    job_id, _ = await repository.upsert_job(db_session, make_job())
    await repository.set_status(db_session, job_id, JobStatus.APPLIED, note="via referral")
    await repository.add_note(db_session, job_id, "spoke with recruiter")

    events = await repository.list_events(db_session, job_id)
    assert len(events) == 2
    # newest first
    assert events[0].event_type == "note"
    assert events[0].note == "spoke with recruiter"
    assert events[1].event_type == "status"
    assert events[1].status == JobStatus.APPLIED
    assert events[1].note == "via referral"


async def test_events_cascade_deleted_with_job(db_session):
    from sqlalchemy import text

    job_id, _ = await repository.upsert_job(db_session, make_job())
    await repository.add_note(db_session, job_id, "temp")
    await db_session.execute(text("DELETE FROM jobs WHERE id = :id").bindparams(id=job_id))
    await db_session.commit()
    assert await repository.list_events(db_session, job_id) == []


async def test_sweep_fails_orphaned_running_dossiers(db_session):
    job_id, _ = await repository.upsert_job(db_session, make_job())
    dossier_id = await create_dossier(db_session, job_id)

    swept = await sweep_stale_running()
    assert swept >= 1

    async with SessionLocal() as session:
        row = await latest_for_job(session, job_id)
    assert row is not None and row.id == dossier_id
    assert row.status == "failed"
    assert "restart" in (row.error or "")


async def test_first_seen_at_survives_reingest(db_session):
    job = make_job()
    job_id, _ = await repository.upsert_job(db_session, job)
    first = (await repository.get_job(db_session, job_id)).first_seen_at
    assert first is not None

    await repository.upsert_job(db_session, job)  # refresh cycle
    again = (await repository.get_job(db_session, job_id)).first_seen_at
    assert again == first  # NEW-badge clock must not reset on refresh
