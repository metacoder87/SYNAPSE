"""Deterministic dossier renderer (R2.3).

The LLM never writes the final document — Python assembles it from verified
claims, so citations cannot be dropped and contradicted claims cannot leak
back in.
"""

from app.agents.research import EvidenceDoc
from app.agents.schemas import (
    JOB_SOURCE_ID,
    NETWORKER_SECTIONS,
    SCOUT_SECTIONS,
    SECTION_TITLES,
    Claim,
    Verdict,
)


def _cite(claim: Claim) -> str:
    ids = [e for e in claim.evidence_ids if e != JOB_SOURCE_ID]
    job_cited = JOB_SOURCE_ID in claim.evidence_ids
    parts = [f"[{e}]" for e in ids]
    if job_cited:
        parts.append("[posting]")
    return " " + "".join(parts) if parts else ""


def render_dossier(
    title: str,
    company: str,
    scout_claims: list[Claim],
    verdicts: dict[int, Verdict],  # index into scout_claims
    networker_claims: list[Claim],
    evidence: list[EvidenceDoc],
) -> str:
    lines: list[str] = [f"# Deep-Dive Dossier: {title} @ {company}", ""]

    supported = [
        (i, c) for i, c in enumerate(scout_claims)
        if verdicts.get(i) and verdicts[i].verdict == "supported"
    ]
    contradicted = [
        (i, c) for i, c in enumerate(scout_claims)
        if verdicts.get(i) and verdicts[i].verdict == "contradicted"
    ]
    unverified = [
        (i, c) for i, c in enumerate(scout_claims)
        if not verdicts.get(i) or verdicts[i].verdict == "insufficient"
    ]

    # Executive summary: first supported claim from the three highest-value sections
    lines.append("**Executive summary**")
    lines.append("")
    summary_added = 0
    for section in ("company_overview", "ai_maturity", "red_flags"):
        for _, c in supported:
            if c.section == section:
                lines.append(f"- {c.text}{_cite(c)}")
                summary_added += 1
                break
    if summary_added == 0:
        lines.append("- *Insufficient verified evidence for a summary — see Unverified notes below.*")
    lines.append("")

    # Research sections (verified facts, then unverified marked clearly)
    for section in SCOUT_SECTIONS:
        sec_supported = [c for _, c in supported if c.section == section]
        sec_unverified = [c for _, c in unverified if c.section == section]
        if not sec_supported and not sec_unverified:
            continue
        lines.append(f"## {SECTION_TITLES[section]}")
        lines.append("")
        for c in sec_supported:
            lines.append(f"- {c.text}{_cite(c)}")
        for c in sec_unverified:
            lines.append(f"- {c.text} *[unverified]*")
        lines.append("")

    # Networking strategy (advice/inference — labeled, not fact-checked)
    lines.append("---")
    lines.append("")
    for section in NETWORKER_SECTIONS:
        sec = [c for c in networker_claims if c.section == section]
        if not sec:
            continue
        lines.append(f"## {SECTION_TITLES[section]} *(inference)*")
        lines.append("")
        for c in sec:
            lines.append(f"- {c.text}{_cite(c)}")
        lines.append("")

    # Sources
    if evidence:
        lines.append("## Sources")
        lines.append("")
        for doc in evidence:
            lines.append(f"- **[{doc.id}]** [{doc.title or doc.url}]({doc.url})")
        lines.append(f"- **[posting]** The job description for *{title}*")
        lines.append("")

    # Verification appendix
    lines.append("## Verification Appendix")
    lines.append("")
    lines.append("| Claim | Verdict | Note |")
    lines.append("|-------|---------|------|")
    for i, c in enumerate(scout_claims):
        v = verdicts.get(i)
        verdict = v.verdict if v else "insufficient"
        note = (v.rationale if v else "not evaluated").replace("|", "/")[:120]
        text = c.text.replace("|", "/")[:100]
        lines.append(f"| {text} | {verdict} | {note} |")
    if contradicted:
        lines.append("")
        lines.append(
            f"*{len(contradicted)} contradicted claim(s) were removed from the report above.*"
        )
    lines.append("")

    return "\n".join(lines)


def quality_stats(scout_claims: list[Claim], verdicts: dict[int, Verdict]) -> tuple[float, float]:
    """(citation_coverage, verified_ratio) for metrics/eval (R4)."""
    if not scout_claims:
        return 0.0, 0.0
    cited = sum(1 for c in scout_claims if c.evidence_ids)
    verified = sum(
        1 for i in range(len(scout_claims))
        if verdicts.get(i) and verdicts[i].verdict == "supported"
    )
    n = len(scout_claims)
    return round(cited / n, 3), round(verified / n, 3)
