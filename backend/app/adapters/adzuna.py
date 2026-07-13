"""Adzuna adapter (P2.3) — global aggregator with strict parameter filtering."""

from datetime import datetime

import httpx

from app.adapters.base import SourceAdapter, request_with_retry
from app.config import settings
from app.models.job import Job

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"
MAX_PAGES = 3


class AdzunaAdapter(SourceAdapter):
    provider = "adzuna"

    async def fetch(self, client: httpx.AsyncClient) -> list[dict]:
        items: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            resp = await request_with_retry(
                client,
                "GET",
                SEARCH_URL.format(page=page),
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": settings.search_keywords_primary,
                    "results_per_page": 50,
                    "max_days_old": 30,
                    "sort_by": "date",
                },
            )
            batch = resp.json().get("results", [])
            items.extend(batch)
            if len(batch) < 50:
                break
        return items

    def parse(self, raw: dict) -> Job:
        location = (raw.get("location") or {}).get("display_name", "")
        title = raw.get("title", "").replace("<strong>", "").replace("</strong>", "")
        description = raw.get("description", "")

        return Job(
            source_provider=self.provider,
            external_reference_id=self.external_id(str(raw["id"])),
            title=title[:255],
            company=((raw.get("company") or {}).get("display_name") or "Unknown")[:255],
            department=(raw.get("category") or {}).get("label"),
            location_string=location[:255] or None,
            is_remote="remote" in f"{title} {location} {description}".lower(),
            job_url=raw.get("redirect_url", ""),
            salary_min=raw.get("salary_min"),
            salary_max=raw.get("salary_max"),
            salary_interval="year" if raw.get("salary_min") else None,
            description_markdown=description.strip() or "(no description provided)",
            posted_at=_parse_dt(raw.get("created")),
            raw_metadata={
                "salary_is_predicted": raw.get("salary_is_predicted"),
                "contract_type": raw.get("contract_type"),
                "contract_time": raw.get("contract_time"),
                "latitude": raw.get("latitude"),
                "longitude": raw.get("longitude"),
            },
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
