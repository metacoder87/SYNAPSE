"""Enrichment trigger logic tests."""

import httpx
import pytest

from app.enrich import enrich_job, should_enrich
from tests.conftest import make_job

FULL_TEXT = "A" * 700


def test_adzuna_always_enriched():
    job = make_job(source_provider="adzuna", description_markdown=FULL_TEXT)
    assert should_enrich(job)


def test_jooble_always_enriched():
    job = make_job(source_provider="jooble", description_markdown=FULL_TEXT)
    assert should_enrich(job)


def test_short_description_enriched():
    job = make_job(source_provider="usajobs", description_markdown="Short snippet.")
    assert should_enrich(job)


def test_ellipsis_truncation_enriched():
    job = make_job(source_provider="usajobs", description_markdown=FULL_TEXT + "…")
    assert should_enrich(job)


def test_full_description_not_enriched():
    job = make_job(source_provider="usajobs", description_markdown=FULL_TEXT + ".")
    assert not should_enrich(job)


async def test_adzuna_enrichment_skips_network_fetch():
    """Adzuna's redirect_url is WAF-blocked for any non-browser request — don't
    even try, so we don't burn a request/log noise on every Adzuna job."""
    job = make_job(source_provider="adzuna", job_url="https://www.adzuna.com/land/ad/1")

    def _fail(request: httpx.Request) -> httpx.Response:
        raise AssertionError("enrich_job must not fetch Adzuna's job_url")

    async with httpx.AsyncClient(transport=httpx.MockTransport(_fail)) as client:
        enriched = await enrich_job(client, job)

    assert enriched is False
