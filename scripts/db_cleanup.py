"""Remove test/fake fixture rows from the jobs table (and their Chroma vectors).

Run from the repo root with the backend venv active:
    python scripts/db_cleanup.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))


async def main() -> None:
    from sqlalchemy import text

    from app.config import settings
    from app.db import SessionLocal

    print(f"Connected via: {settings.database_url.split('@')[-1]}")

    async with SessionLocal() as session:
        rows = (
            await session.execute(
                text("SELECT source_provider, count(*) FROM jobs GROUP BY 1 ORDER BY 2 DESC")
            )
        ).all()
        print("\nBefore cleanup:")
        for provider, n in rows:
            print(f"  {provider}: {n}")

        result = await session.execute(
            text(
                "DELETE FROM jobs WHERE source_provider IN ('test', 'fake') RETURNING id"
            )
        )
        deleted_ids = [str(r[0]) for r in result.all()]
        await session.commit()

    print(f"\nDeleted {len(deleted_ids)} fixture rows from Postgres.")

    if deleted_ids:
        try:
            from app import vector

            vector.delete_job_vectors(deleted_ids)
            print(f"Deleted {len(deleted_ids)} matching Chroma vectors.")
        except Exception as exc:  # noqa: BLE001
            print(f"Chroma cleanup skipped ({exc})")

    async with SessionLocal() as session:
        rows = (
            await session.execute(
                text("SELECT source_provider, count(*) FROM jobs GROUP BY 1 ORDER BY 2 DESC")
            )
        ).all()
        print("\nAfter cleanup:")
        for provider, n in rows:
            print(f"  {provider}: {n}")


if __name__ == "__main__":
    asyncio.run(main())
