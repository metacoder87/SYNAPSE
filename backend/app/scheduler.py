"""APScheduler wiring (P2.6 + P5): ingestion polling + freshness workers."""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.freshness import daily_expiry, heartbeat, weekly_purge
from app.ingest import run_all

logger = logging.getLogger("synapse.scheduler")

scheduler = AsyncIOScheduler()


async def _ingest_tick() -> None:
    stats = await run_all()
    total_new = sum(s.created for s in stats)
    failures = [s.provider for s in stats if s.error]
    logger.info("ingest cycle complete: %d new jobs across %d sources%s",
                total_new, len(stats),
                f" (failed: {', '.join(failures)})" if failures else "")


def start() -> None:
    scheduler.add_job(
        _ingest_tick,
        IntervalTrigger(minutes=settings.ingest_interval_minutes, jitter=120),
        id="ingest_all",
        next_run_time=datetime.now() + timedelta(seconds=20),  # first pull shortly after boot
        max_instances=1,
        coalesce=True,
    )
    # PRD §5 freshness architecture
    scheduler.add_job(daily_expiry, CronTrigger(hour=6, minute=0), id="daily_expiry")
    scheduler.add_job(
        heartbeat, IntervalTrigger(hours=12, jitter=600),
        id="heartbeat", max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        weekly_purge, CronTrigger(day_of_week="sun", hour=7, minute=0), id="weekly_purge"
    )
    scheduler.start()
    logger.info(
        "scheduler started — ingest every %dmin, expiry daily 06:00, "
        "heartbeat every 12h, purge Sundays 07:00",
        settings.ingest_interval_minutes,
    )


def stop() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
