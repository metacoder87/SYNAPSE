"""Prometheus metrics (P7.1/P7.2). Import-safe if prometheus libs are absent."""

import logging

logger = logging.getLogger("synapse.metrics")

try:
    from prometheus_client import Counter, Histogram

    INGEST_RUNS = Counter(
        "synapse_ingest_runs_total",
        "Adapter ingest runs by outcome",
        ["provider", "outcome"],  # outcome: ok | error
    )
    JOBS_CREATED = Counter(
        "synapse_jobs_created_total", "New jobs persisted", ["provider"]
    )
    JOBS_FILTERED = Counter(
        "synapse_jobs_filtered_total", "Jobs discarded by the kill switch", ["provider"]
    )
    FRESHNESS_AFFECTED = Counter(
        "synapse_freshness_affected_total", "Rows affected by freshness workers", ["worker"]
    )
    DOSSIERS = Counter(
        "synapse_dossiers_total", "Deep-dive dossiers by final status", ["status"]
    )
    DOSSIER_DURATION = Histogram(
        "synapse_dossier_duration_seconds",
        "Deep-dive generation wall time",
        buckets=(30, 60, 120, 240, 480, 960, 1920),
    )
    ENABLED = True
except ImportError:  # pragma: no cover
    ENABLED = False
    logger.warning("prometheus_client not installed — metrics disabled")


def record_ingest(provider: str, created: int, filtered: int, error: bool) -> None:
    if not ENABLED:
        return
    INGEST_RUNS.labels(provider=provider, outcome="error" if error else "ok").inc()
    if created:
        JOBS_CREATED.labels(provider=provider).inc(created)
    if filtered:
        JOBS_FILTERED.labels(provider=provider).inc(filtered)


def record_freshness(worker: str, affected: int) -> None:
    if ENABLED:
        FRESHNESS_AFFECTED.labels(worker=worker).inc(affected)


def record_dossier(status: str, duration_seconds: float) -> None:
    if ENABLED:
        DOSSIERS.labels(status=status).inc()
        DOSSIER_DURATION.observe(duration_seconds)


def instrument_app(app) -> None:
    """Attach the FastAPI instrumentator and expose /metrics."""
    if not ENABLED:
        return
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            should_group_status_codes=True,
            excluded_handlers=["/metrics", "/health"],
        ).instrument(app).expose(app, include_in_schema=False)
        logger.info("metrics exposed at /metrics")
    except ImportError:  # pragma: no cover
        logger.warning("prometheus-fastapi-instrumentator not installed — /metrics disabled")
