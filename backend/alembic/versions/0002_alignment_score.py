"""Add alignment_score column for the matching engine (P3.4)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-12

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE jobs ADD COLUMN alignment_score NUMERIC")
    op.execute("CREATE INDEX idx_jobs_alignment ON jobs(alignment_score DESC NULLS LAST)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_alignment")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS alignment_score")
