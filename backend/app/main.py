"""SYNAPSE FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(
    title="Project SYNAPSE",
    description="Systematic Yield Network for AI Placement & Strategic Employment",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """Liveness probe. Extended in Phase 1 with DB/Chroma checks."""
    return {"status": "ok", "service": "synapse-backend", "version": app.version}
