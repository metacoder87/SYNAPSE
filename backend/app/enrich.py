"""Full-description enrichment.

Aggregator APIs (Adzuna, Jooble) return truncated snippets, not full
postings. When a description looks truncated, follow the job URL and extract
the main content of the page with trafilatura. Fail-soft: on any problem the
original snippet is kept.
"""

import logging

import httpx

from app.models.job import Job

logger = logging.getLogger("synapse.enrich")

# Providers whose APIs only ever return snippets
SNIPPET_PROVIDERS = ("adzuna", "jooble")
# Providers whose job_url is a tracked click-through link that their CDN
# blocks for any non-browser request (verified: Adzuna returns a WAF "Access
# Denied" 403 regardless of User-Agent). Fetching it can never succeed, so
# don't burn a request and log noise on every single job from these sources.
NO_FETCH_PROVIDERS = ("adzuna",)
MIN_FULL_LENGTH = 600  # chars — under this we assume truncation
TRUNCATION_MARKERS = ("…", "...", "&hellip;")


def should_enrich(job: Job) -> bool:
    desc = job.description_markdown.strip()
    if any(job.source_provider.startswith(p) for p in SNIPPET_PROVIDERS):
        return True
    if len(desc) < MIN_FULL_LENGTH:
        return True
    return desc.endswith(TRUNCATION_MARKERS)


async def fetch_full_description(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch the posting page and extract readable markdown. None on failure."""
    try:
        import trafilatura

        resp = await client.get(url)
        if resp.status_code != 200 or not resp.text:
            return None
        extracted = trafilatura.extract(
            resp.text,
            output_format="markdown",
            include_links=True,
            include_tables=True,
            favor_recall=True,
        )
        if extracted and len(extracted.strip()) >= MIN_FULL_LENGTH:
            return extracted.strip()
        return None
    except Exception as exc:  # noqa: BLE001
        logger.debug("enrichment failed for %s: %s", url, str(exc)[:150])
        return None


async def enrich_job(client: httpx.AsyncClient, job: Job) -> bool:
    """Replace a truncated description in place. Returns True if enriched."""
    if job.source_provider.startswith(NO_FETCH_PROVIDERS):
        return False
    full = await fetch_full_description(client, job.job_url)
    if full and len(full) > len(job.description_markdown):
        job.raw_metadata = {
            **(job.raw_metadata or {}),
            "original_snippet": job.description_markdown[:1000],
            "description_enriched": True,
        }
        job.description_markdown = full
        return True
    return False
