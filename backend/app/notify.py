"""F4: daily digest notifications via ntfy (free, self-hostable push).

Disabled unless NTFY_TOPIC is set in .env. Subscribe on your phone/browser at
https://ntfy.sh/<your-topic> (pick something unguessable).
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models.job import JobStatus
from app.models.orm import JobRow

logger = logging.getLogger("synapse.notify")


async def send_ntfy(title: str, message: str, priority: str = "default") -> bool:
    if not settings.ntfy_topic:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.ntfy_server.rstrip('/')}/{settings.ntfy_topic}",
                content=message.encode(),
                headers={"Title": title, "Priority": priority, "Tags": "robot"},
            )
            resp.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ntfy send failed: %s", str(exc)[:150])
        return False


async def daily_digest() -> dict:
    """New high-alignment roles from the last 24h + closing-soon applied roles."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        new_jobs = (
            await session.execute(
                select(JobRow)
                .where(
                    JobRow.system_status == JobStatus.ACTIVE,
                    JobRow.first_seen_at >= now - timedelta(hours=24),
                    JobRow.alignment_score >= settings.alignment_threshold,
                )
                .order_by(JobRow.alignment_score.desc())
                .limit(10)
            )
        ).scalars().all()

        closing_soon = (
            await session.execute(
                select(JobRow).where(
                    JobRow.system_status.in_([JobStatus.ACTIVE, JobStatus.APPLIED]),
                    JobRow.closing_date.is_not(None),
                    JobRow.closing_date <= now + timedelta(days=3),
                    JobRow.closing_date >= now,
                )
                .order_by(JobRow.closing_date)
                .limit(10)
            )
        ).scalars().all()

    stats = {"new_high_alignment": len(new_jobs), "closing_soon": len(closing_soon), "sent": False}
    if not settings.ntfy_topic or (not new_jobs and not closing_soon):
        logger.info("digest: %s (notification skipped)", stats)
        return stats

    lines = []
    if new_jobs:
        lines.append(f"{len(new_jobs)} new high-alignment target(s):")
        lines += [
            f"  {float(j.alignment_score):.2f}  {j.title[:50]} @ {j.company[:30]}"
            for j in new_jobs[:5]
        ]
    if closing_soon:
        lines.append(f"{len(closing_soon)} closing within 3 days:")
        lines += [
            f"  {j.closing_date:%b %d}  {j.title[:50]} ({j.system_status.value})"
            for j in closing_soon[:5]
        ]

    stats["sent"] = await send_ntfy("SYNAPSE Daily Digest", "\n".join(lines))
    logger.info("digest: %s", stats)
    return stats
