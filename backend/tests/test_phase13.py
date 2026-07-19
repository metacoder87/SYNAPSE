"""Phase 13 — auth middleware, filter validation, CSV export."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.settings_api import validate_filter_rules

# ---------------------------------------------------------------- E6 auth


@pytest.fixture
def client():
    return TestClient(app)


def test_no_token_configured_means_open(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_token", "")
    assert client.get("/health").status_code == 200


def test_token_gates_api(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_token", "s3cret")
    r = client.get("/config")
    assert r.status_code == 401

    r = client.get("/config", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401

    r = client.get("/config", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200


def test_health_and_metrics_stay_open(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_token", "s3cret")
    assert client.get("/health").status_code == 200
    # /metrics only exists when instrumentator is installed; 401 would be a bug
    assert client.get("/metrics").status_code in (200, 404)


# ---------------------------------------------------------------- E5 validation


def test_valid_rules_accepted():
    assert validate_filter_rules("include:\n  - '\\barchitect'\nexclude: []\n") is None


def test_bad_yaml_rejected():
    assert "YAML" in validate_filter_rules("include: [unclosed")


def test_bad_regex_rejected():
    err = validate_filter_rules("include:\n  - '(unclosed'\n")
    assert err is not None and "regex" in err


def test_non_list_section_rejected():
    err = validate_filter_rules("include: notalist\n")
    assert err is not None and "list" in err


# ---------------------------------------------------------------- F9 export (DB)

from app import repository  # noqa: E402
from tests.conftest import make_job, requires_db  # noqa: E402


@requires_db
async def test_csv_export_contains_jobs(db_session, monkeypatch):
    monkeypatch.setattr(settings, "auth_token", "")
    await repository.upsert_job(db_session, make_job(title="CSV Export Probe"))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/export/jobs.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "CSV Export Probe" in r.text
    assert r.text.splitlines()[0].startswith("title,company,status")
