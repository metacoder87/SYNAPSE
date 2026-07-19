"""R4.2 — Dossier accuracy evaluation harness.

Run ON YOUR MACHINE (needs Ollama + network; each company takes a few minutes):
    python scripts/eval_dossiers.py            # full golden set
    python scripts/eval_dossiers.py --limit 2  # quick check

Scores, per company and aggregate:
  - citation coverage: % of research claims that cite evidence
  - verified ratio:    % of research claims the verifier marked 'supported'
  - golden checks:     claims mentioning founded/HQ terms are string-matched
                       against known facts; mismatches flagged for human review

Writes eval_report.json. Run before AND after any prompt change (R4.4).
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

GENERIC_DESCRIPTION = """# Corporate AI Architect

{company} is seeking a Corporate AI Architect to own enterprise AI strategy:
multi-agent orchestration, LLM platform design, vector databases, and LLMOps.
Principal-level scope advising executive leadership. Remote (US).
"""


def check_golden(claims: list[dict], facts: dict) -> list[str]:
    """Flag claims that mention a golden topic but not the golden value."""
    flags = []
    topic_terms = {
        "founded": ("founded", "founding", "established"),
        "hq": ("headquarter", "based in", "hq"),
    }
    for claim in claims:
        text = claim["claim"].lower()
        for topic, terms in topic_terms.items():
            expected = facts.get(topic, "").lower()
            if expected and any(t in text for t in terms) and expected not in text:
                flags.append(
                    f"[{topic}] expected '{facts[topic]}' — claim: \"{claim['claim'][:120]}\""
                )
    return flags


def main() -> int:
    import yaml

    from app.agents.crew import run_deep_dive
    from app.agents.schemas import PROMPT_VERSION

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    golden = yaml.safe_load(
        (Path(__file__).parents[1] / "backend" / "eval" / "golden.yaml").read_text()
    )["companies"]
    if args.limit:
        golden = golden[: args.limit]

    results = []
    for entry in golden:
        company = entry["name"]
        print(f"\n=== {company} ===")
        start = time.perf_counter()
        try:
            result = run_deep_dive(
                "Corporate AI Architect",
                company,
                GENERIC_DESCRIPTION.format(company=company),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}")
            results.append({"company": company, "error": str(exc)[:300]})
            continue

        flags = check_golden(result.verdicts, entry.get("facts", {}))
        elapsed = round(time.perf_counter() - start, 1)
        row = {
            "company": company,
            "claims": len(result.verdicts),
            "evidence_docs": len(result.evidence),
            "citation_coverage": result.citation_coverage,
            "verified_ratio": result.verified_ratio,
            "golden_flags": flags,
            "seconds": elapsed,
        }
        results.append(row)
        print(f"  claims={row['claims']} sources={row['evidence_docs']} "
              f"coverage={row['citation_coverage']:.2f} verified={row['verified_ratio']:.2f} "
              f"({elapsed}s)")
        for f in flags:
            print(f"  GOLDEN FLAG: {f}")

    ok = [r for r in results if "error" not in r]
    aggregate = {
        "prompt_version": PROMPT_VERSION,
        "companies_evaluated": len(ok),
        "companies_failed": len(results) - len(ok),
        "avg_citation_coverage": round(
            sum(r["citation_coverage"] for r in ok) / len(ok), 3
        ) if ok else 0,
        "avg_verified_ratio": round(
            sum(r["verified_ratio"] for r in ok) / len(ok), 3
        ) if ok else 0,
        "total_golden_flags": sum(len(r["golden_flags"]) for r in ok),
    }

    report = {"aggregate": aggregate, "results": results}
    Path("eval_report.json").write_text(json.dumps(report, indent=2))
    print(f"\n=== AGGREGATE (prompt v{PROMPT_VERSION}) ===")
    print(json.dumps(aggregate, indent=2))
    print("\nFull report: eval_report.json")
    return 0 if aggregate["companies_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
