"""Embedding wrapper (P3.3) — all-MiniLM-L6-v2 via sentence-transformers.

The model import/load is deferred and cached: FastAPI startup stays fast and
test runs that never embed don't pay the ~10s load cost.
"""

from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer  # deferred heavy import

    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Normalized embeddings, so cosine similarity is a plain dot product."""
    vectors = _get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Both inputs must be normalized (embed_texts guarantees this)."""
    return float(sum(x * y for x, y in zip(a, b)))
