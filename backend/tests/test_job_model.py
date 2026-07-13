"""P1.3 — unit tests for the unified Job model (no DB required)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from tests.conftest import make_job


def test_valid_job_parses():
    job = make_job()
    assert job.system_status.value == "active"
    assert job.is_remote is True


def test_bad_url_rejected():
    with pytest.raises(ValidationError, match="http"):
        make_job(job_url="ftp://example.com/job")


def test_negative_salary_rejected():
    with pytest.raises(ValidationError, match="negative"):
        make_job(salary_min=-5)


def test_swapped_salary_range_repaired():
    job = make_job(salary_min=200_000, salary_max=150_000)
    assert job.salary_min == 150_000
    assert job.salary_max == 200_000


def test_naive_datetime_coerced_to_utc():
    job = make_job(posted_at=datetime(2026, 7, 1, 12, 0, 0))
    assert job.posted_at.tzinfo == timezone.utc


def test_blank_title_rejected():
    with pytest.raises(ValidationError, match="empty"):
        make_job(title="   ")
