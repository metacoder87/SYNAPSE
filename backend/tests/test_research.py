"""Phase 10 — evidence pipeline unit tests."""

import pytest

from app.agents.crew import _extract_json
from app.agents.research import EvidenceDoc, chunk_text

# ---------------------------------------------------------------- chunking


def test_chunk_short_text_single_chunk():
    assert chunk_text("hello world") == ["hello world"]


def test_chunk_long_text_overlaps():
    text = "x" * 2000
    chunks = chunk_text(text, size=800, overlap=120)
    assert len(chunks) >= 2
    assert all(len(c) <= 800 for c in chunks)
    # overlap: end of chunk 1 appears at start of chunk 2's coverage
    assert chunks[0][-120:] == chunks[1][:120]


def test_chunk_collapses_whitespace():
    assert chunk_text("a\n\n  b\tc") == ["a b c"]


# ---------------------------------------------------------------- JSON extraction


def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_prose_and_fences():
    raw = 'Sure! Here is the JSON:\n```json\n{"claims": [{"x": "y"}]}\n```\nDone.'
    assert _extract_json(raw) == {"claims": [{"x": "y"}]}


def test_extract_json_nested_braces():
    raw = 'prefix {"a": {"b": {"c": 2}}, "d": [1, 2]} suffix'
    assert _extract_json(raw) == {"a": {"b": {"c": 2}}, "d": [1, 2]}


def test_extract_json_no_object_raises():
    with pytest.raises(ValueError):
        _extract_json("no json here at all")


# ---------------------------------------------------------------- index (needs model)

try:
    from app.embedding import embed_text

    _ = embed_text("warmup")
    EMBEDDINGS_OK = True
except Exception:  # noqa: BLE001
    EMBEDDINGS_OK = False


@pytest.mark.skipif(not EMBEDDINGS_OK, reason="embedding model unavailable")
def test_evidence_index_retrieval():
    from app.agents.research import EvidenceIndex

    docs = [
        EvidenceDoc(id="E1", url="https://a.dev", title="Funding",
                    content="The company raised a forty million dollar Series B round in 2024."),
        EvidenceDoc(id="E2", url="https://b.dev", title="Pool rules",
                    content="Community pool hours are 9am to 5pm; lifeguards on duty weekends."),
    ]
    index = EvidenceIndex(docs)
    results = index.query("How much venture funding did they raise?", k=1)
    assert results[0][0] == "E1"

    ctx = index.context_for("venture capital funding round")
    assert "[E1]" in ctx
