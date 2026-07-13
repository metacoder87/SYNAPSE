"""Shared fixtures. Integration tests need the Docker stack running:

    docker compose up -d
    cd backend && alembic upgrade head
    pytest
"""

import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.job import Job


def _db_available() -> bool:
    async def probe() -> bool:
        try:
            engine = create_async_engine(settings.database_url)
            async with engine.connect():
                pass
            await engine.dispose()
            return True
        except Exception:  # noqa: BLE001
            return False

    return asyncio.new_event_loop().run_until_complete(probe())


requires_db = pytest.mark.skipif(
    not _db_available(), reason="PostgreSQL not reachable — run `docker compose up -d`"
)


@pytest.fixture
async def db_session():
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def make_job(**overrides) -> Job:
    """Valid job payload factory; override any field per-test."""
    defaults = dict(
        source_provider="test",
        external_reference_id=f"test-{uuid.uuid4()}",
        title="Corporate AI Architect",
        company="NeoGrid Systems",
        job_url="https://example.com/jobs/1",
        description_markdown="# Role\nDesign macro-level AI strategy.",
        is_remote=True,
    )
    defaults.update(overrides)
    return Job(**defaults)


@pytest.fixture(scope="session", autouse=True)
def _sweep_fixture_rows_after_session():
    """DB tests commit rows with provider 'test'/'fake'; sweep them at the end
    so the real queue never shows fixtures."""
    yield

    async def purge() -> None:
        try:
            from sqlalchemy import text

            engine = create_async_engine(settings.database_url)
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM jobs WHERE source_provider IN ('test', 'fake')")
                )
            await engine.dispose()
        except Exception:  # noqa: BLE001
            pass  # DB not available — nothing to sweep

    asyncio.new_event_loop().run_until_complete(purge())
