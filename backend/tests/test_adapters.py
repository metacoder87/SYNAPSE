"""P2 — adapter framework and parsing tests (pytest-httpx mocks, no network)."""

import httpx
import pytest

from app.adapters.adzuna import AdzunaAdapter
from app.adapters.base import request_with_retry
from app.adapters.greenhouse import GreenhouseAdapter
from app.adapters.jooble import JoobleAdapter
from app.adapters.rss import RemoteOKAdapter, WeWorkRemotelyAdapter
from app.adapters.usajobs import USAJobsAdapter

# ---------------------------------------------------------------- retry logic


async def test_retry_survives_429_then_succeeds(httpx_mock):
    httpx_mock.add_response(status_code=429, headers={"Retry-After": "0"})
    httpx_mock.add_response(status_code=200, json={"ok": True})

    async with httpx.AsyncClient() as client:
        resp = await request_with_retry(client, "GET", "https://api.example.com/x")
    assert resp.json() == {"ok": True}


async def test_retry_gives_up_after_max_attempts(httpx_mock):
    for _ in range(3):
        httpx_mock.add_response(status_code=429, headers={"Retry-After": "0"})

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.HTTPStatusError):
            await request_with_retry(
                client, "GET", "https://api.example.com/x", retries=2
            )


# ---------------------------------------------------------------- USAJobs

USAJOBS_ITEM = {
    "MatchedObjectId": "800001",
    "MatchedObjectDescriptor": {
        "PositionTitle": "Corporate AI Architect",
        "OrganizationName": "Defense Digital Service",
        "DepartmentName": "Department of Defense",
        "PositionLocationDisplay": "Anywhere in the U.S. (remote job)",
        "PositionURI": "https://www.usajobs.gov/job/800001",
        "ApplyURI": ["https://www.usajobs.gov/job/800001/apply"],
        "PublicationStartDate": "2026-07-01T00:00:00.000",
        "ApplicationCloseDate": "2026-08-15T23:59:59.997",
        "PositionRemuneration": [
            {"MinimumRange": "150000", "MaximumRange": "204000", "RateIntervalCode": "PA"}
        ],
        "QualificationSummary": "Ten years designing enterprise AI systems.",
        "UserArea": {
            "Details": {
                "JobSummary": "Lead macro-level strategic AI design for DoD programs.",
                "SecurityClearance": "Top Secret",
                "LowGrade": "15",
                "HighGrade": "15",
                "MajorDuties": ["Define AI reference architecture", "Advise leadership"],
            }
        },
    },
}


def test_usajobs_parse_extracts_clearance_and_deadline():
    job = USAJobsAdapter().parse(USAJOBS_ITEM)
    assert job.security_clearance == "Top Secret"
    assert job.closing_date is not None and job.closing_date.year == 2026
    assert job.is_remote is True
    assert job.salary_min == 150000
    assert job.external_reference_id == "usajobs:800001"
    assert "Major Duties" in job.description_markdown
    assert job.raw_metadata["low_grade"] == "15"


# ---------------------------------------------------------------- Adzuna

def test_adzuna_parse():
    job = AdzunaAdapter().parse(
        {
            "id": 12345,
            "title": "Principal <strong>AI Architect</strong>",
            "company": {"display_name": "NeoGrid"},
            "location": {"display_name": "Remote, US"},
            "redirect_url": "https://adzuna.com/land/12345",
            "salary_min": 180000.0,
            "salary_max": 220000.0,
            "salary_is_predicted": "0",
            "created": "2026-07-05T10:00:00Z",
            "description": "Own the enterprise AI strategy end to end.",
            "category": {"label": "IT Jobs"},
        }
    )
    assert job.title == "Principal AI Architect"
    assert job.is_remote is True
    assert job.external_reference_id == "adzuna:12345"
    assert job.posted_at.tzinfo is not None


# ---------------------------------------------------------------- Jooble

def test_jooble_parse():
    job = JoobleAdapter().parse(
        {
            "id": 998877,
            "title": "AI Architect (Remote)",
            "company": "Acme Corp",
            "location": "USA",
            "snippet": "Architect LLM platforms.",
            "link": "https://jooble.org/desc/998877",
            "updated": "2026-07-06T00:00:00.000+0000",
            "salary": "$200k",
            "type": "Full-time",
            "source": "acme.com",
        }
    )
    assert job.is_remote is True
    assert job.raw_metadata["salary_text"] == "$200k"


# ---------------------------------------------------------------- Greenhouse

def test_greenhouse_parse_converts_html():
    job = GreenhouseAdapter(company="neogrid").parse(
        {
            "id": 555,
            "title": "Staff AI Architect",
            "absolute_url": "https://boards.greenhouse.io/neogrid/jobs/555",
            "location": {"name": "Remote - US"},
            "departments": [{"name": "Platform"}],
            "updated_at": "2026-07-01T12:00:00-04:00",
            "content": "&lt;h2&gt;About&lt;/h2&gt;&lt;p&gt;Build the &lt;b&gt;future&lt;/b&gt;.&lt;/p&gt;",
        }
    )
    assert job.is_remote is True
    assert job.department == "Platform"
    assert "## About" in job.description_markdown
    assert "**future**" in job.description_markdown
    assert job.external_reference_id == "greenhouse:neogrid:555"


# ---------------------------------------------------------------- RSS

WWR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>WWR</title>
<item>
  <title>NeoGrid Systems: Senior AI Architect</title>
  <link>https://weworkremotely.com/jobs/123</link>
  <guid>https://weworkremotely.com/jobs/123</guid>
  <pubDate>Mon, 06 Jul 2026 09:00:00 +0000</pubDate>
  <category>ai</category>
  <description>&lt;p&gt;Design our &lt;i&gt;agentic&lt;/i&gt; platform.&lt;/p&gt;</description>
</item>
</channel></rss>"""


async def test_wwr_fetch_and_parse(httpx_mock):
    httpx_mock.add_response(status_code=200, text=WWR_XML)
    adapter = WeWorkRemotelyAdapter()

    async with httpx.AsyncClient() as client:
        result = await adapter.run(client)

    assert result.fetched == 1 and result.parsed == 1
    job = result.jobs[0]
    assert job.company == "NeoGrid Systems"
    assert job.title == "Senior AI Architect"
    assert job.is_remote is True
    assert "*agentic*" in job.description_markdown
    assert job.posted_at is not None


def test_remoteok_title_split():
    job = RemoteOKAdapter().parse(
        {
            "title": "Lead AI Architect at CyberDyne",
            "link": "https://remoteok.com/jobs/42",
            "guid": "42",
            "description": "<p>Own model strategy.</p>",
            "pubDate": "Tue, 07 Jul 2026 00:00:00 +0000",
            "category": ["ai"],
        }
    )
    assert job.title == "Lead AI Architect"
    assert job.company == "CyberDyne"


# ---------------------------------------------------------------- fault isolation

async def test_one_bad_payload_does_not_kill_batch(httpx_mock):
    bad_then_good = WWR_XML.replace(
        "<item>",
        "<item><title>Broken</title></item><item>",
        1,
    )
    httpx_mock.add_response(status_code=200, text=bad_then_good)

    async with httpx.AsyncClient() as client:
        result = await WeWorkRemotelyAdapter().run(client)

    assert result.fetched == 2
    assert result.parsed == 1
    assert result.failed == 1
