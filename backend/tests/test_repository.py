"""P1.4 — repository integration tests. Skipped automatically if Postgres is down."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app import repository
from app.models.job import JobStatus
from tests.conftest import make_job, requires_db

pytestmark = requires_db


async def test_upsert_creates_then_updates(db_session):
    job = make_job(title="Original Title")

    job_id, created = await repository.upsert_job(db_session, job)
    assert created is True

    # Same external_reference_id → refresh, not duplicate
    job.title = "Refreshed Title"
    job_id2, created2 = await repository.upsert_job(db_session, job)
    assert created2 is False
    assert job_id == job_id2

    stored = await repository.get_job(db_session, job_id)
    assert stored.title == "Refreshed Title"


async def test_upsert_never_clobbers_user_status(db_session):
    job = make_job()
    job_id, _ = await repository.upsert_job(db_session, job)
    await repository.set_status(db_session, job_id, JobStatus.APPLIED)

    # Re-ingest the same posting (e.g. next cron run)
    await repository.upsert_job(db_session, job)

    stored = await repository.get_job(db_session, job_id)
    assert stored.system_status == JobStatus.APPLIED


async def test_get_active_jobs_filters_status(db_session):
    active = make_job()
    applied = make_job()
    a_id, _ = await repository.upsert_job(db_session, active)
    b_id, _ = await repository.upsert_job(db_session, applied)
    await repository.set_status(db_session, b_id, JobStatus.APPLIED)

    ids = {j.id for j in await repository.get_active_jobs(db_session, limit=1000)}
    assert a_id in ids
    assert b_id not in ids


async def test_expire_past_closing(db_session):
    past = make_job(closing_date=datetime.now(timezone.utc) - timedelta(days=1))
    future = make_job(closing_date=datetime.now(timezone.utc) + timedelta(days=30))
    past_id, _ = await repository.upsert_job(db_session, past)
    future_id, _ = await repository.upsert_job(db_session, future)

    n = await repository.expire_past_closing(db_session)
    assert n >= 1

    assert (await repository.get_job(db_session, past_id)).system_status == JobStatus.EXPIRED
    assert (await repository.get_job(db_session, future_id)).system_status == JobStatus.ACTIVE


async def test_purge_expired_returns_ids_for_vector_cleanup(db_session):
    job = make_job()
    job_id, _ = await repository.upsert_job(db_session, job)
    await repository.set_status(db_session, job_id, JobStatus.EXPIRED)

    # Backdate updated_at past the 14-day window (bypass trigger via direct SQL)
    await db_session.execute(
        text(
            "UPDATE jobs SET updated_at = now() - interval '20 days' WHERE id = :id"
        ).bindparams(id=job_id)
    )
    await db_session.commit()

    deleted = await repository.purge_expired(db_session, older_than_days=14)
    assert job_id in deleted
    assert await repository.get_job(db_session, job_id) is None
