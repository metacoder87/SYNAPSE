"""Lever adapter (P2.4) — targeted company career pages via public postings API."""

from datetime import datetime, timezone

import httpx
from markdownify import markdownify

from app.adapters.base import SourceAdapter, request_with_retry
from app.models.job import Job

POSTINGS_URL = "https://api.lever.co/v0/postings/{company}"


class LeverAdapter(SourceAdapter):
    def __init__(self, company: str):
        self.company = company
        self.provider = f"lever:{company}"

    async def fetch(self, client: httpx.AsyncClient) -> list[dict]:
        resp = await request_with_retry(
            client,
            "GET",
            POSTINGS_URL.format(company=self.company),
            params={"mode": "json"},
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    def parse(self, raw: dict) -> Job:
        categories = raw.get("categories") or {}
        location = categories.get("location", "")
        workplace = raw.get("workplaceType", "")

        description = markdownify(raw.get("description") or "", heading_style="ATX")
        for lst in raw.get("lists") or []:
            section = markdownify(lst.get("content") or "", heading_style="ATX")
            description += f"\n\n## {lst.get('text', 'Details')}\n{section}"

        created_ms = raw.get("createdAt")
        posted_at = (
            datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc) if created_ms else None
        )

        return Job(
            source_provider=self.provider,
            external_reference_id=self.external_id(str(raw["id"])),
            title=raw.get("text", "")[:255],
            company=self.company.replace("-", " ").title()[:255],
            department=categories.get("team"),
            location_string=location[:255] or None,
            is_remote=workplace == "remote" or "remote" in location.lower(),
            job_url=raw.get("hostedUrl", ""),
            apply_url=raw.get("applyUrl"),
            description_markdown=description.strip() or "(no description provided)",
            posted_at=posted_at,
            raw_metadata={
                "commitment": categories.get("commitment"),
                "workplace_type": workplace,
                "country": raw.get("country"),
            },
        )
