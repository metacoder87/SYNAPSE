"""P3.3/P3.4 — embedding + alignment tests with extreme dummy data (PRD §8).

Skipped automatically if sentence-transformers (or its model download)
is unavailable.
"""

import pytest

try:
    from app.embedding import cosine_similarity, embed_text, embed_texts

    _ = embed_text("warmup")
    EMBEDDINGS_OK = True
except Exception:  # noqa: BLE001
    EMBEDDINGS_OK = False

pytestmark = pytest.mark.skipif(
    not EMBEDDINGS_OK, reason="embedding model unavailable (sentence-transformers)"
)

PROFILE_LIKE = (
    "Corporate AI Architect. Enterprise AI strategy, multi-agent orchestration, "
    "LLM platform design, vector databases, remote US."
)
PERFECT = (
    "We seek a Corporate AI Architect to own enterprise AI strategy: multi-agent "
    "systems, LLM platforms, vector databases. Fully remote in the US."
)
MISMATCH = (
    "Seasonal lifeguard for community pool. Swim 500 yards, watch children, "
    "maintain chlorine logs. On-site weekends."
)


def test_embeddings_are_normalized():
    v = embed_text(PROFILE_LIKE)
    assert abs(sum(x * x for x in v) - 1.0) < 1e-4
    assert len(v) == 384  # all-MiniLM-L6-v2


def test_extreme_alignment_separation():
    profile, perfect, mismatch = embed_texts([PROFILE_LIKE, PERFECT, MISMATCH])
    s_perfect = cosine_similarity(profile, perfect)
    s_mismatch = cosine_similarity(profile, mismatch)

    assert s_perfect > 0.7, f"perfect match scored too low: {s_perfect}"
    assert s_mismatch < 0.3, f"total mismatch scored too high: {s_mismatch}"
    assert s_perfect - s_mismatch > 0.4


def test_identical_text_scores_one():
    a, b = embed_texts([PERFECT, PERFECT])
    assert cosine_similarity(a, b) == pytest.approx(1.0, abs=1e-4)
