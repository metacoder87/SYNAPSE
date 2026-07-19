"""SYNAPSE FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app import metrics
from app import scheduler as scheduler_module
from app.api import router as api_router
from app.settings_api import router as settings_router
from app.config import settings
from app.ingest import run_all, run_provider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.artifacts import sweep_orphaned as sweep_artifacts
    from app.dossiers import sweep_orphaned
    from app.tracing import init_tracing

    init_tracing()
    await sweep_orphaned()
    await sweep_artifacts()
    if settings.scheduler_enabled:
        scheduler_module.start()
    yield
    scheduler_module.stop()


app = FastAPI(
    title="Project SYNAPSE",
    description="Systematic Yield Network for AI Placement & Strategic Employment",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(settings_router)

# E6: single-user bearer-token auth (enabled by setting AUTH_TOKEN in .env).
# /health and /metrics stay open for probes and Prometheus.
_AUTH_EXEMPT = {"/health", "/metrics"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    token = settings.auth_token
    if token and request.url.path not in _AUTH_EXEMPT:
        if request.headers.get("authorization") != f"Bearer {token}":
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)
metrics.instrument_app(app)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "synapse-backend", "version": app.version}


@app.post("/ingest/run")
async def trigger_ingest(provider: str | None = None) -> dict:
    """Manually trigger an ingestion cycle (all sources, or one provider)."""
    if provider:
        stats = await run_provider(provider)
        if stats is None:
            raise HTTPException(
                status_code=404,
                detail=f"No enabled adapter named '{provider}'. "
                "Check API keys / company slugs in .env.",
            )
        return asdict(stats)
    return {"results": [asdict(s) for s in await run_all()]}


@app.post("/profile/refresh")
async def refresh_profile() -> dict:
    """Re-embed profile/candidate_profile.md after editing it (P3.2)."""
    from app import matching

    try:
        return matching.refresh_profile()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="profile/candidate_profile.md not found")


@app.post("/filters/reload")
async def reload_filters() -> dict:
    """Reload filter_rules.yaml after editing it (P3.1)."""
    from app import filtering

    filtering.reload_rules()
    return {"status": "ok"}


@app.post("/freshness/run")
async def trigger_freshness(worker: str = "expiry") -> dict:
    """Manually run a freshness worker: expiry | heartbeat | purge (P5)."""
    from app import freshness

    workers = {
        "expiry": freshness.daily_expiry,
        "heartbeat": freshness.heartbeat,
        "purge": freshness.weekly_purge,
    }
    if worker not in workers:
        raise HTTPException(status_code=422, detail=f"worker must be one of {list(workers)}")
    return {"worker": worker, "affected": await workers[worker]()}
