"""Unified Job Pydantic model (PRD §3) — every source adapter maps into this.

This is the single contract between ingestion and the database. Validators
enforce salary sanity, URL shape, and timezone-aware datetimes so bad payloads
fail loudly at the adapter boundary instead of corrupting the DB.
"""

import enum
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class JobStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    REJECTED = "rejected"


class Job(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Core Identity
    id: uuid.UUID | None = None
    source_provider: str = Field(max_length=50)
    external_reference_id: str = Field(max_length=255)

    # Display Data
    title: str = Field(max_length=255)
    company: str = Field(max_length=255)
    department: str | None = Field(default=None, max_length=255)
    location_string: str | None = Field(default=None, max_length=255)
    is_remote: bool = False

    # Links & Pay
    job_url: str
    apply_url: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_interval: str | None = Field(default=None, max_length=50)

    # Specialized Requirements
    security_clearance: str | None = Field(default=None, max_length=100)

    # Matching engine (P3.4) — cosine similarity vs candidate profile
    alignment_score: float | None = Field(default=None, ge=-1.0, le=1.0)

    # The Payload
    description_markdown: str

    # Time & Lifecycle
    posted_at: datetime | None = None
    closing_date: datetime | None = None
    system_status: JobStatus = JobStatus.ACTIVE
    last_verified_at: datetime | None = None
    updated_at: datetime | None = None
    first_seen_at: datetime | None = None

    # Overflow Safety Net
    raw_metadata: dict | None = None

    # --- Validators -------------------------------------------------------

    @field_validator("job_url", "apply_url")
    @classmethod
    def url_must_be_http(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http(s)://, got: {v[:60]}")
        return v

    @field_validator("salary_min", "salary_max")
    @classmethod
    def salary_non_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("salary cannot be negative")
        return v

    @field_validator("posted_at", "closing_date", "last_verified_at", "updated_at", "first_seen_at")
    @classmethod
    def datetime_must_be_aware(cls, v: datetime | None) -> datetime | None:
        """Naive datetimes are assumed UTC (many boards omit offsets)."""
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("title", "company", "description_markdown")
    @classmethod
    def strip_and_require_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("field cannot be empty or whitespace")
        return v

    @model_validator(mode="after")
    def salary_range_sane(self) -> "Job":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            # Some boards swap the fields; repair rather than reject.
            self.salary_min, self.salary_max = self.salary_max, self.salary_min
        return self
