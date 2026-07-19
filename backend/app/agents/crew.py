"""Deep-dive research pipeline v2 (Phase 10).

Stages (deterministic Python orchestration over the CrewAI LLM interface,
all local via Ollama, traced by Phoenix through LiteLLM):

  1. gather_evidence  — multi-query Serper/DDG retrieval + page extraction (R1)
  2. disambiguation   — LLM gate drops evidence about the wrong company (R1.3)
  3. scout            — JSON claims with per-claim evidence citations (R2.1)
  4. networker        — JSON outreach strategy grounded in the posting (R2.1)
  5. verify           — per-claim, temperature-0 verdicts against cited
                        evidence (R2.2)
  6. render           — Python assembles the final markdown; citations are
                        structural, not stylistic (R2.3)
"""

import logging
import re

from app.agents import render, research
from app.agents.llm import call_json as _call_json
from app.agents.llm import extract_json as _extract_json  # noqa: F401 (test import)
from app.agents.llm import make_llm
from app.agents.schemas import (
    JOB_SOURCE_ID,
    NETWORKER_SECTIONS,
    PROMPT_VERSION,
    SCOUT_SECTIONS,
    SECTION_TITLES,
    Claim,
    ClaimSet,
    DeepDiveResult,
    Verdict,
)
from app.config import settings

logger = logging.getLogger("synapse.agents")

MAX_CLAIMS_PER_SECTION = 4
JSON_RETRIES = 2

SECTION_TOPICS = {
    "company_overview": "business model products industry headquarters size funding",
    "ai_maturity": "artificial intelligence machine learning strategy engineering",
    "remote_culture": "remote work culture benefits work-life balance reviews",
    "red_flags": "layoffs lawsuit controversy negative reviews turnover",
}


def _make_llm(temperature: float, model: str | None = None):
    return make_llm(temperature, model)


# ---------------------------------------------------------------- stages

def _disambiguate(llm, docs: list[research.EvidenceDoc],
                  company: str, title: str, description: str) -> list[research.EvidenceDoc]:
    """R1.3: drop evidence that is about a different company with a similar name."""
    if not docs:
        return docs
    listing = "\n".join(f"{d.id}: {d.title} — {d.content[:200]}" for d in docs)
    prompt = (
        f"A candidate is researching the company \"{company}\", which is hiring "
        f"a \"{title}\". Excerpt of the job posting:\n{description[:800]}\n\n"
        f"Below are search results. Some may be about a DIFFERENT company that "
        f"happens to have a similar name.\n\n{listing}\n\n"
        "Return JSON: {\"relevant_ids\": [\"E1\", ...]} listing ONLY the ids that "
        "are about this specific company. When unsure, include the id."
    )
    try:
        result = _call_json(llm, prompt)
        keep = {str(i).strip().upper() for i in result.get("relevant_ids", [])}
        kept = [d for d in docs if d.id in keep]
        if kept:
            dropped = len(docs) - len(kept)
            if dropped:
                logger.info("disambiguation dropped %d/%d docs", dropped, len(docs))
            return kept
    except Exception as exc:  # noqa: BLE001
        logger.warning("disambiguation failed (%s) — keeping all docs", str(exc)[:120])
    return docs


def _scout_claims(llm, index: research.EvidenceIndex,
                  company: str, title: str, description: str) -> ClaimSet:
    """R2.1: research claims, each citing evidence ids.

    One small LLM call per section keeps each prompt well inside the local
    model's default context window (no truncation risk) and makes the JSON
    easier for an 8B model to get right."""
    all_claims: list[Claim] = []
    for section, topic in SECTION_TOPICS.items():
        evidence = index.context_for(f"{company} {topic}", k=4, max_chars=2000)
        section_title = SECTION_TITLES.get(section, section)
        prompt = (
            "You are a company research analyst. You know NOTHING about any "
            "company except what appears in the EVIDENCE and the JOB POSTING "
            "excerpt below.\n\n"
            f"# JOB POSTING ({title} at {company}, excerpt)\n{description[:1200]}\n\n"
            f"# EVIDENCE\n{evidence}\n\n"
            f"Produce at most {MAX_CLAIMS_PER_SECTION} factual claims STRICTLY about "
            f"\"{section_title}\" (topic keywords: {topic}) — a claim that is true "
            "and well-evidenced but belongs under a DIFFERENT section (e.g. general "
            "company description, when the section is red flags) must NOT be "
            "included here. Every claim MUST cite the evidence ids (e.g. \"E2\") it "
            f"came from, or \"{JOB_SOURCE_ID}\" if it comes from the job posting. If "
            f"none of the evidence is actually about {topic}, return an EMPTY claims "
            "list — never restate general company information just to fill the quota.\n\n"
            "Return JSON only:\n"
            f'{{"claims": [{{"text": "...", "evidence_ids": ["E1"], "section": "{section}"}}]}}'
        )
        try:
            data = _call_json(llm, prompt)
            parsed = ClaimSet.model_validate(data)
            for c in parsed.claims:
                c.section = section  # trust our loop, not the model
            all_claims.extend(parsed.claims[:MAX_CLAIMS_PER_SECTION])
        except Exception as exc:  # noqa: BLE001
            logger.warning("scout section '%s' failed: %s", section, str(exc)[:120])
    return ClaimSet(claims=all_claims)


def _networker_claims(llm, company: str, title: str, description: str) -> ClaimSet:
    prompt = (
        "You are a career strategist analyzing a job posting for organizational "
        "signals. Base everything on the posting itself.\n\n"
        f"# JOB POSTING ({title} at {company})\n{description[:2000]}\n\n"
        f"Sections: {list(NETWORKER_SECTIONS)}.\n"
        "- hiring_owner: the likely role/title that owns this hire (never invent names)\n"
        "- why_open: plausible inference for why the role exists\n"
        "- outreach_angles: exactly 3 specific talking points connecting a senior "
        "AI architect's background to this company's needs\n"
        f"Cite \"{JOB_SOURCE_ID}\" for claims grounded in the posting.\n\n"
        "Return JSON only:\n"
        '{"claims": [{"text": "...", "evidence_ids": ["JOB"], "section": "hiring_owner"}]}'
    )
    data = _call_json(llm, prompt)
    claims = ClaimSet.model_validate(data)
    claims.claims = [c for c in claims.claims if c.section in NETWORKER_SECTIONS]
    return claims


_NUM_TOKEN_RE = re.compile(r"\$?\d[\d,\.]*\s*(?:million|billion|thousand|[kmb])?\b", re.I)


def _normalize_numeric(text: str) -> str:
    t = text.lower().replace(",", "").replace("$", "")
    return (t.replace(" million", "m").replace("million", "m")
             .replace(" billion", "b").replace("billion", "b")
             .replace(" thousand", "k").replace("thousand", "k"))


def _deterministic_precheck(claim_text: str, evidence_text: str) -> str | None:
    """R3.1: every number in a claim must literally appear in its evidence.

    Catches the classic hallucinations (funding amounts, years, headcounts)
    without spending a single token. Returns a failure reason, or None."""
    tokens = _NUM_TOKEN_RE.findall(claim_text)
    if not tokens:
        return None
    haystack = _normalize_numeric(evidence_text)
    for tok in tokens:
        needle = _normalize_numeric(tok).strip()
        if needle and needle not in haystack:
            return f"number '{tok.strip()}' not found in cited evidence"
    return None


def _verify_claims(verifier_llm, claims: list[Claim], index: research.EvidenceIndex,
                   description: str) -> dict[int, Verdict]:
    """R2.2: per-claim verdicts against cited + retrieved evidence, temperature 0."""
    verdicts: dict[int, Verdict] = {}
    for i, claim in enumerate(claims):
        cited_ids = [e for e in claim.evidence_ids if e != JOB_SOURCE_ID]
        context_parts = []
        if cited_ids:
            context_parts.append(index.chunks_for_doc_ids(cited_ids))
        retrieved = index.query(claim.text, k=3)
        context_parts.extend(f"[{d}] {c}" for d, c, _ in retrieved)
        if JOB_SOURCE_ID in claim.evidence_ids:
            context_parts.append(f"[{JOB_SOURCE_ID}] {description[:1500]}")
        context = "\n\n".join(context_parts)[:4000] or "(no evidence available)"

        # R3.1: deterministic gate first — numbers must appear in evidence
        precheck = _deterministic_precheck(claim.text, context)
        if precheck:
            verdicts[i] = Verdict(verdict="insufficient", rationale=precheck)
            continue

        prompt = (
            "You are a strict fact-checker. Judge the CLAIM strictly against the "
            "EVIDENCE. You have no other knowledge.\n\n"
            f"CLAIM: {claim.text}\n\nEVIDENCE:\n{context}\n\n"
            "Return JSON only: {\"verdict\": \"supported\"|\"contradicted\"|"
            "\"insufficient\", \"rationale\": \"one short sentence\"}"
        )
        try:
            data = _call_json(verifier_llm, prompt, retries=1)
            verdicts[i] = Verdict.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("verdict failed for claim %d: %s", i, str(exc)[:120])
            verdicts[i] = Verdict(verdict="insufficient", rationale="verifier error")
    return verdicts


# ---------------------------------------------------------------- pipeline

def run_deep_dive(title: str, company: str, description: str,
                  progress_cb=None) -> DeepDiveResult:
    """Blocking pipeline; call via asyncio.to_thread."""
    def _progress(stage: str) -> None:
        if progress_cb:
            try:
                progress_cb(stage)
            except Exception:  # noqa: BLE001
                pass

    llm = _make_llm(temperature=0.4)
    verifier = _make_llm(temperature=0.0, model=settings.ollama_verifier_model or None)
    description = description[:6000]

    _progress("gathering web evidence")
    logger.info("dive[%s]: gathering evidence", company)
    docs = research.gather_evidence(company)
    docs = _disambiguate(verifier, docs, company, title, description)
    # Re-id sequentially after the gate so citations stay dense
    for n, d in enumerate(docs, start=1):
        d.id = f"E{n}"
    index = research.EvidenceIndex(docs)

    _progress(f"extracting claims from {len(docs)} sources")
    logger.info("dive[%s]: extracting claims from %d evidence docs", company, len(docs))
    scout = _scout_claims(llm, index, company, title, description)
    networker = _networker_claims(llm, company, title, description)

    _progress(f"fact-checking {len(scout.claims)} claims")
    logger.info("dive[%s]: verifying %d claims", company, len(scout.claims))
    verdicts = _verify_claims(verifier, scout.claims, index, description)

    _progress("rendering dossier")
    markdown = render.render_dossier(
        title, company, scout.claims, verdicts, networker.claims, docs
    )
    coverage, verified = render.quality_stats(scout.claims, verdicts)
    logger.info("dive[%s]: done — coverage=%.2f verified=%.2f", company, coverage, verified)

    return DeepDiveResult(
        markdown=markdown,
        evidence=[d.as_dict() for d in docs],
        verdicts=[
            {"claim": c.text, "section": c.section,
             "verdict": verdicts[i].verdict, "rationale": verdicts[i].rationale}
            for i, c in enumerate(scout.claims)
        ],
        prompt_version=PROMPT_VERSION,
        citation_coverage=coverage,
        verified_ratio=verified,
    )
