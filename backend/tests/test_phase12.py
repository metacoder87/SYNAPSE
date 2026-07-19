"""Phase 12 — deterministic validator, keyword gap, artifact persistence."""

import pytest

from app.agents.crew import _deterministic_precheck
from app.agents.tailor import keyword_gap

# ---------------------------------------------------------------- R3.1 validators


def test_matching_number_passes():
    assert _deterministic_precheck(
        "The company raised $40 million in 2024.",
        "In 2024 the firm announced a $40,000,000 raise... raised $40 million",
    ) is None


def test_fabricated_amount_caught():
    reason = _deterministic_precheck(
        "The company raised $75 million.",
        "The company raised a $40 million Series B.",
    )
    assert reason is not None and "75" in reason


def test_fabricated_year_caught():
    reason = _deterministic_precheck(
        "Founded in 2015.",
        "The company was founded in 2019 in Austin.",
    )
    assert reason is not None and "2015" in reason


def test_claim_without_numbers_defers_to_llm():
    assert _deterministic_precheck(
        "The company has a strong remote culture.",
        "totally unrelated evidence",
    ) is None


def test_million_normalization():
    assert _deterministic_precheck(
        "Raised $40M.",
        "secured a $40 million round",
    ) is None


# ---------------------------------------------------------------- F1 keyword gap


def test_keyword_gap_flags_missing_terms():
    job = ("Kubernetes Kubernetes Kubernetes Terraform Terraform experience "
           "with Kafka Kafka required. Python Python Python.")
    resume = "Python expert. FastAPI, PostgreSQL."
    gaps = keyword_gap(job, resume)
    assert "kubernetes" in gaps
    assert "terraform" in gaps
    assert "kafka" in gaps
    assert "python" not in gaps  # present in resume


def test_keyword_gap_ignores_stopwords_and_rare_terms():
    job = "The ideal candidate will have experience and ability. Zookeeper mentioned once."
    gaps = keyword_gap(job, "empty resume")
    assert "the" not in gaps and "experience" not in gaps
    assert "zookeeper" not in gaps  # frequency < 2


# ---------------------------------------------------------------- artifacts (DB)

from app import artifacts, repository  # noqa: E402
from tests.conftest import make_job, requires_db  # noqa: E402


@requires_db
async def test_artifact_lifecycle(db_session):
    job_id, _ = await repository.upsert_job(db_session, make_job())

    art_id = await artifacts.create(db_session, job_id, "tailor")
    row = await artifacts.latest(db_session, job_id, "tailor")
    assert row is not None and row.id == art_id and row.status == "running"

    await artifacts._finish(art_id, status="complete", content="# Pack")
    row = await artifacts.latest(db_session, job_id, "tailor")
    assert row.status == "complete" and row.content_markdown == "# Pack"

    latest_map = await artifacts.latest_all(db_session, job_id)
    assert set(latest_map) == {"tailor"}


@requires_db
async def test_artifact_sweep(db_session):
    job_id, _ = await repository.upsert_job(db_session, make_job())
    await artifacts.create(db_session, job_id, "interview")

    swept = await artifacts.sweep_orphaned()
    assert swept >= 1
    row = await artifacts.latest(db_session, job_id, "interview")
    assert row.status == "failed"
