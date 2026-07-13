"""Data freshness workers (PRD §5, P5): expiry, heartbeat, purge."""

import asyncio
import logging
from collections import defaultdict
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models.job import JobStatus
from app.models.orm import JobRow
from app import metrics, repository, vector

logger = logging.getLogger("synapse.freshness")

FILLED_FLAGS = (
    "this position has been filled",
    "position has been filled",
    "no longer accepting applications",
    "this job is no longer available",
    "job not found",
    "posting not found",
    "this vacancy is closed",
)

GENERIC_LANDING_PATHS = ("", "/", "/jobs", "/careers", "/search")

PER_DOMAIN_DELAY_SECONDS = 1.0


async def daily_expiry() -> int:
    """Deterministic expiry: closing_date in the past → expired."""
    async with SessionLocal() as session:
        n = await repository.expire_past_closing(session)
    metrics.record_freshness("expiry", n)
    logger.info("daily expiry: %d jobs marked expired", n)
    return n


def _looks_dead(resp: httpx.Response, original_url: str) -> str | None:
    """Return a reason string if the posting looks dead, else None."""
    if resp.status_code in (404, 410):
        return f"HTTP {resp.status_code}"
    if resp.history:  # we were redirected
        final = urlparse(str(resp.url))
        original = urlparse(original_url)
        if final.path.rstrip("/").lower() in GENERIC_LANDING_PATHS or (
            final.netloc != original.netloc and final.path.rstrip("/") in GENERIC_LANDING_PATHS
        ):
            return f"redirected to generic page ({resp.url})"
    if resp.status_code == 200:
        body = resp.text[:30000].lower()
        for flag in FILLED_FLAGS:
            if flag in body:
                return f"page text: '{flag}'"
    return None


async def _check_domain(client: httpx.AsyncClient, jobs: list[tuple], dead: list) -> None:
    """Check one domain's jobs sequentially with a politeness delay."""
    for job_id, url in jobs:
        try:
            resp = await client.get(url)
            reason = _looks_dead(resp, url)
            if reason:
                dead.append((job_id, reason))
        except httpx.HTTPError as exc:
            # Network errors are inconclusive — never expire on them
            logger.debug("heartbeat inconclusive for %s: %s", url, exc)
        await asyncio.sleep(PER_DOMAIN_DELAY_SECONDS)


async def heartbeat() -> int:
    """Async heartbeat worker (12h): probe active job URLs, expire dead ones."""
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(JobRow.id, JobRow.job_url).where(
                    JobRow.system_status == JobStatus.ACTIVE
                )
            )
        ).all()

    by_domain: dict[str, list[tuple]] = defaultdict(list)
    for job_id, url in rows:
        by_domain[urlparse(url).netloc].append((job_id, url))

    dead: list[tuple] = []
    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SYNAPSE-heartbeat/0.1)"},
    ) as client:
        await asyncio.gather(
            *(_check_domain(client, jobs, dead) for jobs in by_domain.values())
        )

    async with SessionLocal() as session:
        for job_id, reason in dead:
            await repository.set_status(session, job_id, JobStatus.EXPIRED)
            logger.info("heartbeat expired %s — %s", job_id, reason)

    metrics.record_freshness("heartbeat", len(dead))
    logger.info("heartbeat: %d/%d active jobs expired", len(dead), len(rows))
    return len(dead)


async def weekly_purge() -> int:
    """Delete stale expired rows from Postgres AND their Chroma vectors."""
    async with SessionLocal() as session:
        deleted_ids = await repository.purge_expired(session, older_than_days=14)
    if deleted_ids:
        try:
            vector.delete_job_vectors([str(i) for i in deleted_ids])
        except Exception as exc:  # noqa: BLE001
            logger.error("purge: Chroma vector cleanup failed — %s", exc)
    metrics.record_freshness("purge", len(deleted_ids))
    logger.info("weekly purge: %d jobs deleted", len(deleted_ids))
    return len(deleted_ids)
