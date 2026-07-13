"""ChromaDB access layer (P1.5).

Two collections:
- `jobs`: one document per job, keyed by the Postgres UUID (string form),
  so Postgres remains the source of truth and vectors can be purged in sync.
- `candidate_profile`: single document holding the primary candidate profile
  embedding (populated in Phase 3, P3.2).
"""

from functools import lru_cache

import chromadb
from chromadb.api.models.Collection import Collection

from app.config import settings

JOBS_COLLECTION = "jobs"
PROFILE_COLLECTION = "candidate_profile"
PROFILE_DOC_ID = "primary"

# Cosine space so query distances map directly to the Alignment Score (P3.4):
# similarity = 1 - distance
_COLLECTION_METADATA = {"hnsw:space": "cosine"}


@lru_cache(maxsize=1)
def get_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)


def get_jobs_collection() -> Collection:
    return get_client().get_or_create_collection(
        JOBS_COLLECTION, metadata=_COLLECTION_METADATA
    )


def get_profile_collection() -> Collection:
    return get_client().get_or_create_collection(
        PROFILE_COLLECTION, metadata=_COLLECTION_METADATA
    )


def add_job_vector(job_id: str, embedding: list[float], document: str, metadata: dict) -> None:
    get_jobs_collection().upsert(
        ids=[job_id], embeddings=[embedding], documents=[document], metadatas=[metadata]
    )


def delete_job_vectors(job_ids: list[str]) -> None:
    """Called after repository.purge_expired to keep stores consistent."""
    if job_ids:
        get_jobs_collection().delete(ids=job_ids)


def heartbeat() -> bool:
    try:
        get_client().heartbeat()
        return True
    except Exception:  # noqa: BLE001
        return False
