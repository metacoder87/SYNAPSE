"""SQLAlchemy ORM mapping for the jobs table (PRD §4)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.job import JobStatus


class JobRow(Base):
    __tablename__ = "jobs"

    # Core Identity
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_reference_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Display Data
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str | None] = mapped_column(String(255))
    location_string: Mapped[str | None] = mapped_column(String(255))
    is_remote: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    # Links & Pay
    job_url: Mapped[str] = mapped_column(Text, nullable=False)
    apply_url: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[float | None] = mapped_column(Numeric)
    salary_max: Mapped[float | None] = mapped_column(Numeric)
    salary_interval: Mapped[str | None] = mapped_column(String(50))

    # Specialized Requirements
    security_clearance: Mapped[str | None] = mapped_column(String(100))

    # Matching engine (P3.4)
    alignment_score: Mapped[float | None] = mapped_column(Numeric)

    # The Payload
    description_markdown: Mapped[str] = mapped_column(Text, nullable=False)

    # Time & Lifecycle
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    system_status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=lambda e: [m.value for m in e]),
        server_default=JobStatus.ACTIVE.value,
    )
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    # Referenced by PRD §5 purge logic; maintained by DB trigger (see migration 0001)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    # The Overflow Safety Net (Schema-on-Read)
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)


class DossierRow(Base):
    __tablename__ = "dossiers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="running")
    content_markdown: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
