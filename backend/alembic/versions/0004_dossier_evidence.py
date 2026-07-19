"""Dossier evidence, verdicts, prompt_version, quality stats (Phase 10)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-18

"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE dossiers ADD COLUMN evidence JSONB")
    op.execute("ALTER TABLE dossiers ADD COLUMN verdicts JSONB")
    op.execute("ALTER TABLE dossiers ADD COLUMN prompt_version VARCHAR(20)")
    op.execute("ALTER TABLE dossiers ADD COLUMN citation_coverage NUMERIC")
    op.execute("ALTER TABLE dossiers ADD COLUMN verified_ratio NUMERIC")


def downgrade() -> None:
    for col in ("evidence", "verdicts", "prompt_version", "citation_coverage", "verified_ratio"):
        op.execute(f"ALTER TABLE dossiers DROP COLUMN IF EXISTS {col}")
