"""Phase 11: first_seen_at, dive progress, status_events timeline

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-18

"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # U3: when SYNAPSE first ingested the job (posted_at is source-reported and
    # often null; this is our own reliable clock for "NEW" badges and digests)
    op.execute(
        "ALTER TABLE jobs ADD COLUMN first_seen_at TIMESTAMP WITH TIME ZONE "
        "NOT NULL DEFAULT NOW()"
    )

    # E2: live pipeline stage for running dives
    op.execute("ALTER TABLE dossiers ADD COLUMN progress VARCHAR(120)")

    # U2: application timeline
    op.execute(
        """
        CREATE TABLE status_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            event_type VARCHAR(20) NOT NULL DEFAULT 'status',
            status job_status,
            note TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_status_events_job ON status_events(job_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS status_events")
    op.execute("ALTER TABLE dossiers DROP COLUMN IF EXISTS progress")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS first_seen_at")
