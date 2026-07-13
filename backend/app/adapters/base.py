"""Adapter framework (P2.1): base class + fault-tolerant HTTP helper."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

from app.models.job import Job

logger = logging.getLogger("synapse.adapters")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    retries: int = 3,
    backoff_base: float = 2.0,
    **kwargs,
) -> httpx.Response:
    """HTTP request with exponential backoff; honors Retry-After on 429."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code not in RETRYABLE_STATUS:
                resp.raise_for_status()
                return resp
            if attempt == retries:
                resp.raise_for_status()
            retry_after = resp.headers.get("Retry-After")
            delay = (
                float(retry_after)
                if retry_after and retry_after.replace(".", "", 1).isdigit()
                else backoff_base**attempt
            )
            logger.warning("HTTP %s from %s — retry %d/%d in %.1fs",
                           resp.status_code, url, attempt + 1, retries, delay)
            await asyncio.sleep(delay)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt == retries:
                raise
            delay = backoff_base**attempt
            logger.warning("Transport error on %s (%s) — retry %d/%d in %.1fs",
                           url, exc, attempt + 1, retries, delay)
            await asyncio.sleep(delay)
    raise last_exc or RuntimeError("unreachable")


@dataclass
class AdapterResult:
    provider: str
    fetched: int = 0
    parsed: int = 0
    failed: int = 0
    jobs: list[Job] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SourceAdapter(ABC):
    """One external job source. Subclasses implement fetch() and parse()."""

    provider: str

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> list[dict]:
        """Return raw item payloads from the source."""

    @abstractmethod
    def parse(self, raw: dict) -> Job:
        """Map one raw payload into the unified Job model."""

    def external_id(self, source_id: str) -> str:
        """Namespace IDs by provider so sources can never collide."""
        return f"{self.provider}:{source_id}"

    async def run(self, client: httpx.AsyncClient) -> AdapterResult:
        """Fetch + parse with per-item fault isolation: one bad payload
        never kills the batch."""
        result = AdapterResult(provider=self.provider)
        raw_items = await self.fetch(client)
        result.fetched = len(raw_items)
        for raw in raw_items:
            try:
                result.jobs.append(self.parse(raw))
                result.parsed += 1
            except Exception as exc:  # noqa: BLE001
                result.failed += 1
                result.errors.append(str(exc)[:200])
        if result.failed:
            logger.warning("%s: %d/%d payloads failed to parse",
                           self.provider, result.failed, result.fetched)
        return result
