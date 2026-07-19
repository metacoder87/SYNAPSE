"""F2: Interview prep agent — grounded in the verified dossier when available."""

import logging
import re
from pathlib import Path

from app.agents.llm import call_text, make_llm

logger = logging.getLogger("synapse.interview")

PROFILE_PATH = Path(__file__).parents[2] / "profile" / "candidate_profile.md"


def _profile_text() -> str:
    text = PROFILE_PATH.read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()[:2500]


def run_interview_prep(
    title: str, company: str, description: str, dossier_markdown: str | None
) -> str:
    """Blocking; call via asyncio.to_thread. Returns the prep pack markdown."""
    llm = make_llm(temperature=0.4)
    description = description[:2200]
    profile = _profile_text()
    dossier_context = (
        f"# VERIFIED COMPANY DOSSIER (from prior deep-dive research)\n"
        f"{dossier_markdown[:2500]}\n\n"
        if dossier_markdown
        else "(No dossier available — base company questions on the posting only.)\n\n"
    )

    questions = call_text(llm, (
        "You are an interview coach for a senior AI architecture candidate.\n\n"
        f"# JOB POSTING ({title} at {company})\n{description}\n\n"
        f"{dossier_context}"
        "Produce markdown with exactly these sections:\n"
        "## Likely Technical Questions — 5 questions this specific posting "
        "implies, hardest first, each with a one-line 'what they're really "
        "asking' note\n"
        "## Likely Behavioral Questions — 4 questions tied to the role's "
        "seniority and scope\n"
        "## Company-Specific Questions — 3 questions grounded in the dossier "
        "facts (or posting if no dossier)\n"
        "Output only the markdown."
    ))

    star = call_text(llm, (
        "You are an interview coach. Build STAR answer skeletons from the "
        "candidate's actual background — use ONLY what the profile states.\n\n"
        f"# CANDIDATE PROFILE\n{profile}\n\n"
        f"# JOB POSTING ({title} at {company})\n{description[:1200]}\n\n"
        "Pick the 3 experiences from the profile most relevant to this role. "
        "For each, output:\n"
        "### Story: <short name>\n"
        "- **Situation/Task**: one line\n"
        "- **Action**: 2-3 bullets in the candidate's voice\n"
        "- **Result**: one line (only metrics the profile supports)\n"
        "- **Deploy against**: which likely question this story answers\n"
        "Output only the markdown."
    ))

    asks = call_text(llm, (
        f"# JOB POSTING ({title} at {company})\n{description[:1200]}\n\n"
        f"{dossier_context}"
        "Write 5 sharp questions the candidate should ask the interviewers — "
        "questions that signal senior-level thinking (org design, AI strategy "
        "maturity, decision rights, success metrics) and surface red flags. "
        "One line each with a brief 'listen for' note. Output only a markdown "
        "numbered list."
    ))

    grounding = "verified dossier + posting" if dossier_markdown else "posting only"
    return "\n".join([
        f"# Interview Prep: {title} @ {company}",
        "",
        f"*Grounding: {grounding}. Run DEEP DIVE first for company-specific depth.*"
        if not dossier_markdown else
        "*Grounded in your verified deep-dive dossier.*",
        "",
        questions,
        "",
        "## Your STAR Stories",
        "",
        star,
        "",
        "## Questions to Ask Them",
        "",
        asks,
    ])
