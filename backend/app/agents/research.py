"""Evidence pipeline (R1): multi-query retrieval → extraction → RAG index.

Runs synchronously inside the deep-dive worker thread.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.embedding import cosine_similarity, embed_texts

logger = logging.getLogger("synapse.research")

MAX_DOCS = 8
MAX_DOC_CHARS = 2500
RESULTS_PER_QUERY = 2
CHUNK_CHARS = 800
CHUNK_OVERLAP = 120

QUERY_TEMPLATES = (
    '"{company}" company',
    '"{company}" funding OR acquisition OR revenue',
    '"{company}" engineering blog OR technology stack',
    '"{company}" glassdoor OR "employee reviews"',
    '"{company}" news OR layoffs',
)

_SKIP_DOMAINS = ("linkedin.com/jobs", "indeed.com", "ziprecruiter.com")


@dataclass
class EvidenceDoc:
    id: str
    url: str
    title: str
    content: str
    retrieved_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "content": self.content[:MAX_DOC_CHARS],
            "retrieved_at": self.retrieved_at,
        }


# ---------------------------------------------------------------- search

def serper_search(query: str, num: int = 5) -> list[dict]:
    resp = httpx.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
        json={"q": query, "num": num},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    results = [
        {"title": r.get("title", ""), "body": r.get("snippet", ""), "href": r.get("link", "")}
        for r in data.get("organic", [])[:num]
    ]
    kg = data.get("knowledgeGraph")
    if kg:
        facts = ", ".join(f"{k}: {v}" for k, v in (kg.get("attributes") or {}).items())
        results.insert(0, {
            "title": f"[Knowledge Graph] {kg.get('title', '')} ({kg.get('type', '')})",
            "body": f"{kg.get('description', '')} {facts}".strip(),
            "href": kg.get("website", "") or "https://google.com",
        })
    return results


def ddg_search(query: str, num: int = 5) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    return [
        {"title": r.get("title", ""), "body": r.get("body", ""), "href": r.get("href", "")}
        for r in DDGS().text(query, max_results=num)
    ]


def search(query: str, num: int = 5) -> list[dict]:
    """Serper primary, DDG fallback (R1.0)."""
    if settings.serper_api_key:
        try:
            return serper_search(query, num)
        except Exception as exc:  # noqa: BLE001
            logger.warning("serper failed (%s), falling back to DDG", str(exc)[:120])
    try:
        return ddg_search(query, num)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ddg failed: %s", str(exc)[:120])
        return []


# ---------------------------------------------------------------- gathering

def _extract_page(client: httpx.Client, url: str) -> str | None:
    try:
        import trafilatura

        resp = client.get(url)
        if resp.status_code != 200 or not resp.text:
            return None
        return trafilatura.extract(
            resp.text, output_format="markdown", include_tables=True, favor_recall=True
        )
    except Exception:  # noqa: BLE001
        return None


def gather_evidence(company: str) -> list[EvidenceDoc]:
    """R1.1/R1.2: multi-query search, fetch pages, build evidence docs."""
    docs: list[EvidenceDoc] = []
    seen_urls: set[str] = set()

    with httpx.Client(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SYNAPSE-research/2.0)"},
    ) as client:
        for template in QUERY_TEMPLATES:
            if len(docs) >= MAX_DOCS:
                break
            for r in search(template.format(company=company), num=4)[:RESULTS_PER_QUERY]:
                url = r.get("href", "")
                if not url or url in seen_urls:
                    continue
                if any(d in url for d in _SKIP_DOMAINS):
                    continue
                seen_urls.add(url)

                content = _extract_page(client, url)
                # Fall back to the search snippet — still citable evidence
                body = (content or r.get("body", "")).strip()
                if len(body) < 40:
                    continue
                docs.append(
                    EvidenceDoc(
                        id=f"E{len(docs) + 1}",
                        url=url,
                        title=r.get("title", "")[:200],
                        content=body[:MAX_DOC_CHARS],
                    )
                )
                if len(docs) >= MAX_DOCS:
                    break

    logger.info("evidence: %d docs from %d urls considered", len(docs), len(seen_urls))
    return docs


# ---------------------------------------------------------------- RAG index

def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += size - overlap
    return chunks


class EvidenceIndex:
    """In-memory chunked embedding index over evidence docs (R1.4).

    Kept in-process (not a persistent Chroma collection) because it lives
    exactly as long as one dive; normalized embeddings via the same MiniLM
    model used for job matching.
    """

    def __init__(self, docs: list[EvidenceDoc]):
        self.docs = {d.id: d for d in docs}
        self._chunks: list[tuple[str, str]] = []  # (doc_id, chunk)
        for d in docs:
            for ch in chunk_text(d.content):
                self._chunks.append((d.id, ch))
        self._vectors = (
            embed_texts([c for _, c in self._chunks]) if self._chunks else []
        )

    def query(self, text: str, k: int = 4) -> list[tuple[str, str, float]]:
        """Top-k (doc_id, chunk, score)."""
        if not self._chunks:
            return []
        qv = embed_texts([text])[0]
        scored = [
            (doc_id, chunk, cosine_similarity(qv, vec))
            for (doc_id, chunk), vec in zip(self._chunks, self._vectors)
        ]
        scored.sort(key=lambda t: t[2], reverse=True)
        return scored[:k]

    def context_for(self, topic: str, k: int = 4, max_chars: int = 2400) -> str:
        """Formatted evidence context: '[E2] chunk text…' lines."""
        out, used = [], 0
        for doc_id, chunk, _ in self.query(topic, k):
            line = f"[{doc_id}] {chunk}"
            if used + len(line) > max_chars:
                break
            out.append(line)
            used += len(line)
        return "\n\n".join(out) if out else "(no evidence retrieved)"

    def chunks_for_doc_ids(self, doc_ids: list[str], max_chars: int = 1800) -> str:
        out, used = [], 0
        for doc_id in doc_ids:
            doc = self.docs.get(doc_id)
            if not doc:
                continue
            line = f"[{doc.id}] ({doc.url}) {doc.content}"
            take = line[: max(0, max_chars - used)]
            if not take:
                break
            out.append(take)
            used += len(take)
        return "\n\n".join(out)
