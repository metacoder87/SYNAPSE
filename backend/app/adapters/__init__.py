"""Source adapter registry (PRD §3).

Every external source maps into the unified Job model through an adapter.
`enabled_adapters()` returns only sources whose credentials/config exist,
so missing API keys degrade gracefully instead of crashing the scheduler.
"""

from app.adapters.adzuna import AdzunaAdapter
from app.adapters.base import SourceAdapter
from app.adapters.greenhouse import GreenhouseAdapter
from app.adapters.jooble import JoobleAdapter
from app.adapters.lever import LeverAdapter
from app.adapters.rss import RemoteOKAdapter, WeWorkRemotelyAdapter
from app.adapters.usajobs import USAJobsAdapter
from app.config import settings


def all_adapters() -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []

    if settings.usajobs_api_key and settings.usajobs_user_agent:
        adapters.append(USAJobsAdapter())
    if settings.adzuna_app_id and settings.adzuna_app_key:
        adapters.append(AdzunaAdapter())
    if settings.jooble_api_key:
        adapters.append(JoobleAdapter())
    for slug in _split(settings.greenhouse_companies):
        adapters.append(GreenhouseAdapter(company=slug))
    for slug in _split(settings.lever_companies):
        adapters.append(LeverAdapter(company=slug))

    # RSS feeds need no credentials — always on
    adapters.append(WeWorkRemotelyAdapter())
    adapters.append(RemoteOKAdapter())
    return adapters


def get_adapter(provider: str) -> SourceAdapter | None:
    return next((a for a in all_adapters() if a.provider == provider), None)


def _split(csv: str) -> list[str]:
    return [s.strip() for s in csv.split(",") if s.strip()]
