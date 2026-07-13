"""Jooble adapter (P2.3) — POST-based aggregator API."""

from datetime import datetime

import httpx

from app.adapters.base import SourceAdapter, request_with_retry
from app.config import settings
from app.models.job import Job

API_URL = "https://jooble.org/api/{key}"


class JoobleAdapter(SourceAdapter):
    provider = "jooble"

    async def fetch(self, client: httpx.AsyncClient) -> list[dict]:
        resp = await request_with_retry(
            client,
            "POST",
            API_URL.format(key=settings.jooble_api_key),
            json={
                "keywords": settings.search_keywords_primary,
                "location": "USA",
                "page": 1,
            },
        )
        return resp.json().get("jobs", [])

    def parse(self, raw: dict) -> Job:
        title = raw.get("title", "")
        location = raw.get("location", "")
        snippet = raw.get("snippet", "")

        return Job(
            source_provider=self.provider,
            external_reference_id=self.external_id(str(raw["id"])),
            title=title[:255],
            company=(raw.get("company") or "Unknown")[:255],
            location_string=location[:255] or None,
            is_remote="remote" in f"{title} {location}".lower(),
            job_url=raw.get("link", ""),
            description_markdown=snippet.strip() or "(no description provided)",
            posted_at=_parse_dt(raw.get("updated")),
            raw_metadata={
                "salary_text": raw.get("salary"),
                "job_type": raw.get("type"),
                "source_board": raw.get("source"),
            },
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
