"""E1 — orphaned dossier sweep. Skipped automatically if Postgres is down."""

from sqlalchemy import delete, select, update

from app import dossiers, repository
from app.models.orm import DossierRow
from tests.conftest import make_job, requires_db

pytestmark = requires_db


async def test_sweep_orphaned_fails_stuck_running_but_leaves_completed(db_session):
    """A backend restart kills the worker behind any dossier still marked
    'running' — start_deep_dive() then refuses a retry because it sees one
    "in progress" (see app/api.py). sweep_orphaned() must fail those rows so
    a restart can never permanently wedge a job's dive, while leaving
    already-finished dossiers untouched."""
    stuck_job_id, _ = await repository.upsert_job(db_session, make_job())
    stuck_id = await dossiers.create_dossier(db_session, stuck_job_id)

    done_job_id, _ = await repository.upsert_job(db_session, make_job())
    done_id = await dossiers.create_dossier(db_session, done_job_id)
    await db_session.execute(
        update(DossierRow).where(DossierRow.id == done_id).values(status="complete")
    )
    await db_session.commit()

    try:
        swept = await dossiers.sweep_orphaned()
        assert swept >= 1

        rows = {
            row.id: row
            for row in (
                await db_session.execute(
                    select(DossierRow).where(DossierRow.id.in_([stuck_id, done_id]))
                )
            ).scalars()
        }

        assert rows[stuck_id].status == "failed"
        assert rows[stuck_id].error == "server restarted before completion"
        assert rows[stuck_id].completed_at is not None

        assert rows[done_id].status == "complete"
        assert rows[done_id].error is None
    finally:
        await db_session.execute(delete(DossierRow).where(DossierRow.id.in_([stuck_id, done_id])))
        await db_session.commit()
