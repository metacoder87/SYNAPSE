"""Create jobs table, job_status enum, indexes, updated_at trigger (PRD §4 + §5 gap fix)

Revision ID: 0001
Revises:
Create Date: 2026-07-12

"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")  # gen_random_uuid on PG < 13 semantics

    op.execute(
        "CREATE TYPE job_status AS ENUM "
        "('active', 'expired', 'applied', 'interviewing', 'rejected')"
    )

    op.execute(
        """
        CREATE TABLE jobs (
            -- Core Identity
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_provider VARCHAR(50) NOT NULL,
            external_reference_id VARCHAR(255) UNIQUE NOT NULL,

            -- Display Data
            title VARCHAR(255) NOT NULL,
            company VARCHAR(255) NOT NULL,
            department VARCHAR(255),
            location_string VARCHAR(255),
            is_remote BOOLEAN DEFAULT FALSE,

            -- Links & Pay
            job_url TEXT NOT NULL,
            apply_url TEXT,
            salary_min NUMERIC,
            salary_max NUMERIC,
            salary_interval VARCHAR(50),

            -- Specialized Requirements
            security_clearance VARCHAR(100),

            -- The Payload
            description_markdown TEXT NOT NULL,

            -- Time & Lifecycle
            posted_at TIMESTAMP WITH TIME ZONE,
            closing_date TIMESTAMP WITH TIME ZONE,

            system_status job_status DEFAULT 'active',
            last_verified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

            -- The Overflow Safety Net (Schema-on-Read)
            raw_metadata JSONB
        )
        """
    )

    op.execute("CREATE INDEX idx_jobs_status ON jobs(system_status)")
    op.execute("CREATE INDEX idx_jobs_closing_date ON jobs(closing_date)")

    # updated_at is referenced by the PRD §5 purge logic but absent from the §4
    # schema — maintained automatically by trigger so app code can't forget it.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Auto-stamp unless the statement explicitly set updated_at
            -- (lets maintenance scripts and tests backdate deliberately)
            IF NEW.updated_at IS NOT DISTINCT FROM OLD.updated_at THEN
                NEW.updated_at = NOW();
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_jobs_updated_at
        BEFORE UPDATE ON jobs
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_jobs_updated_at ON jobs")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at")
    op.execute("DROP TABLE IF EXISTS jobs")
    op.execute("DROP TYPE IF EXISTS job_status")
