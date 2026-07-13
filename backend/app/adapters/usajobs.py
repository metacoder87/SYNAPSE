"""USAJobs adapter (P2.2) — highest-priority source (PRD §3).

Extracts security clearance requirements and concrete application deadlines,
which most boards don't provide. API docs: https://developer.usajobs.gov/
"""

from datetime import datetime

import httpx

from app.adapters.base import SourceAdapter, request_with_retry
from app.config import settings
from app.models.job import Job

SEARCH_URL = "https://data.usajobs.gov/api/search"


class USAJobsAdapter(SourceAdapter):
    provider = "usajobs"

    async def fetch(self, client: httpx.AsyncClient) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            resp = await request_with_retry(
                client,
                "GET",
                SEARCH_URL,
                headers={
                    "Authorization-Key": settings.usajobs_api_key,
                    "User-Agent": settings.usajobs_user_agent,
                    "Host": "data.usajobs.gov",
                },
                params={
                    "Keyword": settings.search_keywords_primary,
                    "ResultsPerPage": 100,
                    "Page": page,
                },
            )
            data = resp.json()
            batch = data.get("SearchResult", {}).get("SearchResultItems", [])
            items.extend(batch)
            pages = int(data.get("SearchResult", {}).get("UserArea", {}).get("NumberOfPages", 1))
            if page >= pages or not batch:
                break
            page += 1
        return items

    def parse(self, raw: dict) -> Job:
        d = raw["MatchedObjectDescriptor"]
        details = d.get("UserArea", {}).get("Details", {})

        salary_min = salary_max = None
        salary_interval = None
        pay = d.get("PositionRemuneration") or []
        if pay:
            salary_min = float(pay[0].get("MinimumRange") or 0) or None
            salary_max = float(pay[0].get("MaximumRange") or 0) or None
            salary_interval = pay[0].get("RateIntervalCode")

        location = d.get("PositionLocationDisplay", "")
        is_remote = "anywhere in the u.s" in location.lower() or bool(
            details.get("RemoteIndicator")
        )

        description = details.get("JobSummary") or d.get("QualificationSummary") or ""
        duties = details.get("MajorDuties")
        if duties:
            duties_text = "\n".join(f"- {x}" for x in duties) if isinstance(duties, list) else str(duties)
            description = f"{description}\n\n## Major Duties\n{duties_text}"

        return Job(
            source_provider=self.provider,
            external_reference_id=self.external_id(raw["MatchedObjectId"]),
            title=d.get("PositionTitle", "")[:255],
            company=d.get("OrganizationName", "US Federal Government")[:255],
            department=(d.get("DepartmentName") or None),
            location_string=location[:255] or None,
            is_remote=is_remote,
            job_url=d.get("PositionURI", ""),
            apply_url=(d.get("ApplyURI") or [None])[0],
            salary_min=salary_min,
            salary_max=salary_max,
            salary_interval=salary_interval,
            security_clearance=(details.get("SecurityClearance") or None),
            description_markdown=description.strip() or "(no description provided)",
            posted_at=_parse_dt(d.get("PublicationStartDate")),
            closing_date=_parse_dt(d.get("ApplicationCloseDate")),
            raw_metadata={
                "low_grade": details.get("LowGrade"),
                "high_grade": details.get("HighGrade"),
                "promotion_potential": details.get("PromotionPotential"),
                "relocation": details.get("Relocation"),
                "hiring_path": d.get("UserArea", {}).get("Details", {}).get("HiringPath"),
                "position_schedule": [
                    s.get("Name") for s in (d.get("PositionSchedule") or [])
                ],
            },
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
