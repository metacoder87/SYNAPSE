"""Greenhouse adapter (P2.4) — targeted company career pages via public JSON API."""

import html
from datetime import datetime

import httpx
from markdownify import markdownify

from app.adapters.base import SourceAdapter, request_with_retry
from app.models.job import Job

BOARD_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"


class GreenhouseAdapter(SourceAdapter):
    def __init__(self, company: str):
        self.company = company
        self.provider = f"greenhouse:{company}"

    async def fetch(self, client: httpx.AsyncClient) -> list[dict]:
        resp = await request_with_retry(
            client,
            "GET",
            BOARD_URL.format(company=self.company),
            params={"content": "true"},
        )
        return resp.json().get("jobs", [])

    def parse(self, raw: dict) -> Job:
        location = (raw.get("location") or {}).get("name", "")
        departments = [d.get("name") for d in (raw.get("departments") or []) if d.get("name")]
        # Greenhouse double-escapes HTML entities in `content`
        content_html = html.unescape(raw.get("content") or "")
        description = markdownify(content_html, heading_style="ATX").strip()

        return Job(
            source_provider=self.provider,
            external_reference_id=self.external_id(str(raw["id"])),
            title=raw.get("title", "")[:255],
            company=self.company.replace("-", " ").title()[:255],
            department=(departments[0] if departments else None),
            location_string=location[:255] or None,
            is_remote="remote" in location.lower(),
            job_url=raw.get("absolute_url", ""),
            description_markdown=description or "(no description provided)",
            posted_at=_parse_dt(raw.get("updated_at")),
            raw_metadata={
                "internal_job_id": raw.get("internal_job_id"),
                "requisition_id": raw.get("requisition_id"),
                "all_departments": departments,
                "offices": [o.get("name") for o in (raw.get("offices") or [])],
            },
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
