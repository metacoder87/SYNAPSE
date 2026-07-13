"""Matching engine (P3.2–P3.4): profile embedding + Alignment Score."""

import logging
from pathlib import Path

from app import vector
from app.embedding import cosine_similarity, embed_text

logger = logging.getLogger("synapse.matching")

PROFILE_PATH = Path(__file__).parents[1] / "profile" / "candidate_profile.md"

# Module-level cache so ingest doesn't hit Chroma per job
_profile_embedding: list[float] | None = None


def refresh_profile() -> dict:
    """Re-embed candidate_profile.md and store it in Chroma (P3.2)."""
    global _profile_embedding
    text = PROFILE_PATH.read_text(encoding="utf-8")
    embedding = embed_text(text)
    vector.get_profile_collection().upsert(
        ids=[vector.PROFILE_DOC_ID],
        embeddings=[embedding],
        documents=[text],
        metadatas=[{"path": str(PROFILE_PATH)}],
    )
    _profile_embedding = embedding
    logger.info("candidate profile re-embedded (%d chars)", len(text))
    return {"status": "ok", "profile_chars": len(text), "vector_dim": len(embedding)}


def get_profile_embedding() -> list[float] | None:
    """Cached profile embedding; falls back to Chroma, then to re-embedding."""
    global _profile_embedding
    if _profile_embedding is not None:
        return _profile_embedding
    try:
        stored = vector.get_profile_collection().get(
            ids=[vector.PROFILE_DOC_ID], include=["embeddings"]
        )
        if len(stored["ids"]) > 0:
            _profile_embedding = list(stored["embeddings"][0])
            return _profile_embedding
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not load profile from Chroma: %s", exc)
    try:
        refresh_profile()
        return _profile_embedding
    except Exception as exc:  # noqa: BLE001
        logger.error("profile embedding unavailable: %s", exc)
        return None


def score_job_text(title: str, description: str) -> tuple[float | None, list[float]]:
    """Embed a job and compute its Alignment Score against the profile.

    Returns (score, job_embedding). Score is None when no profile exists —
    the job is still embedded and stored so scores can be backfilled.
    """
    job_embedding = embed_text(f"{title}\n\n{description}")
    profile = get_profile_embedding()
    if profile is None:
        return None, job_embedding
    return round(cosine_similarity(profile, job_embedding), 4), job_embedding


def invalidate_profile_cache() -> None:
    global _profile_embedding
    _profile_embedding = None
