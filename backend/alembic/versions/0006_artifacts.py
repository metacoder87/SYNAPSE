"""Artifacts table for tailor/interview packs (Phase 12)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-18

"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE artifacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            kind VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'running',
            content_markdown TEXT,
            error TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_artifacts_job_kind ON artifacts(job_id, kind, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS artifacts")
