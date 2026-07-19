"""Phase 10 — deterministic renderer tests (no LLM, no network, always run)."""

from app.agents.render import quality_stats, render_dossier
from app.agents.research import EvidenceDoc
from app.agents.schemas import Claim, Verdict


def _fixture():
    evidence = [
        EvidenceDoc(id="E1", url="https://neogrid.dev/about", title="About NeoGrid",
                    content="NeoGrid was founded in 2019 in Austin."),
        EvidenceDoc(id="E2", url="https://news.example.com/ng", title="NeoGrid raises B",
                    content="NeoGrid raised a $40M Series B."),
    ]
    scout = [
        Claim(text="NeoGrid was founded in 2019.", evidence_ids=["E1"], section="company_overview"),
        Claim(text="NeoGrid raised a $40M Series B.", evidence_ids=["E2"], section="company_overview"),
        Claim(text="NeoGrid is a Fortune 500 company.", evidence_ids=["E2"], section="company_overview"),
        Claim(text="They deploy LLM agents in production.", evidence_ids=[], section="ai_maturity"),
    ]
    verdicts = {
        0: Verdict(verdict="supported", rationale="stated in E1"),
        1: Verdict(verdict="supported", rationale="stated in E2"),
        2: Verdict(verdict="contradicted", rationale="E2 says Series B startup"),
        3: Verdict(verdict="insufficient", rationale="no evidence"),
    }
    networker = [
        Claim(text="Likely owned by the VP of Platform Engineering.",
              evidence_ids=["JOB"], section="hiring_owner"),
    ]
    return evidence, scout, verdicts, networker


def test_supported_claims_rendered_with_citations():
    evidence, scout, verdicts, networker = _fixture()
    md = render_dossier("AI Architect", "NeoGrid", scout, verdicts, networker, evidence)
    assert "NeoGrid was founded in 2019. [E1]" in md
    assert "$40M Series B. [E2]" in md


def test_contradicted_claim_removed_from_body():
    evidence, scout, verdicts, networker = _fixture()
    md = render_dossier("AI Architect", "NeoGrid", scout, verdicts, networker, evidence)
    body = md.split("## Verification Appendix")[0]
    assert "Fortune 500" not in body
    assert "1 contradicted claim(s) were removed" in md


def test_insufficient_claim_marked_unverified():
    evidence, scout, verdicts, networker = _fixture()
    md = render_dossier("AI Architect", "NeoGrid", scout, verdicts, networker, evidence)
    assert "They deploy LLM agents in production. *[unverified]*" in md


def test_sources_and_appendix_present():
    evidence, scout, verdicts, networker = _fixture()
    md = render_dossier("AI Architect", "NeoGrid", scout, verdicts, networker, evidence)
    assert "## Sources" in md
    assert "[About NeoGrid](https://neogrid.dev/about)" in md
    assert "| Claim | Verdict | Note |" in md
    assert "contradicted" in md


def test_networker_section_labeled_inference():
    evidence, scout, verdicts, networker = _fixture()
    md = render_dossier("AI Architect", "NeoGrid", scout, verdicts, networker, evidence)
    assert "## Likely Hiring Owner *(inference)*" in md
    assert "[posting]" in md


def test_quality_stats():
    _, scout, verdicts, _ = _fixture()
    coverage, verified = quality_stats(scout, verdicts)
    assert coverage == 0.75   # 3 of 4 claims cite evidence
    assert verified == 0.5    # 2 of 4 supported
