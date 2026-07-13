"""Dossiers table for CrewAI deep-dive reports (P6)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-13

"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE dossiers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            status VARCHAR(20) NOT NULL DEFAULT 'running',
            content_markdown TEXT,
            error TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE
        )
        """
    )
    op.execute("CREATE INDEX idx_dossiers_job ON dossiers(job_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dossiers")
