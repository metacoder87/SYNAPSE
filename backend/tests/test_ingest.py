"""P2.6 — ingest pipeline integration test (requires Postgres)."""

import httpx

from app.adapters.base import SourceAdapter
from app.db import SessionLocal
from app.ingest import run_one
from tests.conftest import make_job, requires_db

pytestmark = requires_db


class FakeAdapter(SourceAdapter):
    provider = "fake"

    async def fetch(self, client: httpx.AsyncClient) -> list[dict]:
        return [{"n": 1}, {"n": 2}, {"bad": True}]

    def parse(self, raw: dict) -> object:
        if raw.get("bad"):
            raise ValueError("malformed payload")
        return make_job(
            external_reference_id=f"fake:{raw['n']}",
            title=f"Fake Job {raw['n']}",
        )


async def test_run_one_persists_and_counts():
    stats = await run_one(FakeAdapter())

    assert stats.fetched == 3
    assert stats.parsed == 2
    assert stats.parse_failed == 1
    assert stats.created + stats.refreshed == 2
    assert stats.persist_failed == 0

    # Second run: same external IDs → refreshed, not duplicated
    stats2 = await run_one(FakeAdapter())
    assert stats2.created == 0
    assert stats2.refreshed == 2

    # Cleanup
    from sqlalchemy import text

    async with SessionLocal() as session:
        await session.execute(text("DELETE FROM jobs WHERE source_provider = 'fake'"))
        await session.commit()
