"""RSS adapters (P2.5) — WeWorkRemotely & RemoteOK unstructured XML feeds.

The adapter isolates each item's <description> block (PRD §3), converts the
HTML to markdown, and namespaces the GUID for dedupe.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx
from markdownify import markdownify

from app.adapters.base import SourceAdapter, request_with_retry
from app.models.job import Job


class _RSSAdapter(SourceAdapter):
    feed_url: str
    default_company: str

    async def fetch(self, client: httpx.AsyncClient) -> list[dict]:
        resp = await request_with_retry(
            client,
            "GET",
            self.feed_url,
            headers={"User-Agent": "SYNAPSE/0.1 (job aggregation; personal use)"},
        )
        root = ET.fromstring(resp.text)
        items = []
        for item in root.iter("item"):
            items.append(
                {
                    "title": _text(item, "title"),
                    "link": _text(item, "link"),
                    "guid": _text(item, "guid") or _text(item, "link"),
                    "description": _text(item, "description"),
                    "pubDate": _text(item, "pubDate"),
                    "category": [c.text for c in item.findall("category") if c.text],
                }
            )
        return items

    def parse(self, raw: dict) -> Job:
        title, company = self._split_title(raw.get("title", ""))
        description = markdownify(raw.get("description") or "", heading_style="ATX")

        return Job(
            source_provider=self.provider,
            external_reference_id=self.external_id(raw["guid"]),
            title=title[:255],
            company=company[:255],
            location_string="Remote",
            is_remote=True,  # both feeds are remote-only by definition
            job_url=raw.get("link", ""),
            description_markdown=description.strip() or "(no description provided)",
            posted_at=_parse_rfc822(raw.get("pubDate")),
            raw_metadata={"categories": raw.get("category", [])},
        )

    def _split_title(self, title: str) -> tuple[str, str]:
        """Feeds encode 'Company: Job Title' in a single element."""
        if ":" in title:
            company, _, role = title.partition(":")
            return role.strip() or title, company.strip() or self.default_company
        return title, self.default_company


class WeWorkRemotelyAdapter(_RSSAdapter):
    provider = "weworkremotely"
    feed_url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    default_company = "Unknown (WWR)"


class RemoteOKAdapter(_RSSAdapter):
    provider = "remoteok"
    feed_url = "https://remoteok.com/remote-ai-jobs.rss"
    default_company = "Unknown (RemoteOK)"

    def _split_title(self, title: str) -> tuple[str, str]:
        """RemoteOK uses 'Job Title at Company' format."""
        if " at " in title:
            role, _, company = title.rpartition(" at ")
            return role.strip() or title, company.strip() or self.default_company
        return title, self.default_company


def _text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _parse_rfc822(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
