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
    invalidate_sentences = True  # noqa: F841
    globals()["_profile_sentences"] = None
    globals()["_profile_sentence_vecs"] = None
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
    global _profile_embedding, _profile_sentences, _profile_sentence_vecs
    _profile_embedding = None
    _profile_sentences = None
    _profile_sentence_vecs = None


# ---------------------------------------------------------------- U1: why this score

_profile_sentences: list[str] | None = None
_profile_sentence_vecs: list[list[float]] | None = None


def _profile_sentence_index() -> tuple[list[str], list[list[float]]]:
    global _profile_sentences, _profile_sentence_vecs
    if _profile_sentences is None:
        import re

        from app.embedding import embed_texts

        text = PROFILE_PATH.read_text(encoding="utf-8")
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        raw = re.split(r"(?<=[.!?])\s+|\n+", text)
        sentences = [
            s.strip().lstrip("#").strip()
            for s in raw
            if len(s.strip()) > 40 and not s.strip().startswith("#")
        ]
        _profile_sentences = sentences[:60]
        _profile_sentence_vecs = embed_texts(_profile_sentences) if _profile_sentences else []
    return _profile_sentences, _profile_sentence_vecs


def explain_score(title: str, description: str, top_k: int = 3) -> list[dict]:
    """Top profile phrases driving this job's Alignment Score (U1)."""
    from app.embedding import cosine_similarity, embed_text

    sentences, vecs = _profile_sentence_index()
    if not sentences:
        return []
    job_vec = embed_text(f"{title}\n\n{description[:4000]}")
    scored = sorted(
        (
            {"phrase": s, "similarity": round(cosine_similarity(job_vec, v), 3)}
            for s, v in zip(sentences, vecs)
        ),
        key=lambda d: d["similarity"],
        reverse=True,
    )
    return scored[:top_k]
