"""P1.5 — ChromaDB smoke tests. Skipped automatically if Chroma is down."""

import uuid

import pytest

from app import vector

requires_chroma = pytest.mark.skipif(
    not vector.heartbeat(), reason="ChromaDB not reachable — run `docker compose up -d`"
)

pytestmark = requires_chroma


def test_upsert_query_delete_roundtrip():
    job_id = str(uuid.uuid4())
    fake_embedding = [0.1] * 384  # all-MiniLM-L6-v2 dimensionality

    vector.add_job_vector(
        job_id,
        embedding=fake_embedding,
        document="Corporate AI Architect at NeoGrid Systems",
        metadata={"source_provider": "test"},
    )

    col = vector.get_jobs_collection()
    res = col.query(query_embeddings=[fake_embedding], n_results=1)
    assert res["ids"][0][0] == job_id
    # Identical vector in cosine space → distance ~0 → similarity ~1
    assert res["distances"][0][0] < 0.01

    vector.delete_job_vectors([job_id])
    assert col.get(ids=[job_id])["ids"] == []


def test_profile_collection_exists():
    col = vector.get_profile_collection()
    assert col.name == vector.PROFILE_COLLECTION
