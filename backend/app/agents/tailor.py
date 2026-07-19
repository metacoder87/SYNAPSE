"""F1: Resume & cover-letter tailor agent (fully local, privacy-first).

Selects and rephrases from profile/master_resume.md — instructed never to
invent experience. Keyword-gap analysis is deterministic Python.
"""

import logging
import re
from collections import Counter
from pathlib import Path

from app.agents.llm import call_text, make_llm

logger = logging.getLogger("synapse.tailor")

RESUME_PATH = Path(__file__).parents[2] / "profile" / "master_resume.md"

_STOPWORDS = frozenset(
    """the a an and or of to in for with on at by from as is are will be this
    that our your you we they it their its have has must can may should
    ability experience years work team teams role position job company
    including required preferred qualifications responsibilities benefits
    equal opportunity employer about us apply application candidates
    strong excellent proven track record etc more than least""".split()
)


def read_master_resume() -> str:
    text = RESUME_PATH.read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def keyword_gap(job_description: str, resume: str, top_n: int = 12) -> list[str]:
    """Deterministic: frequent job-posting terms missing from the resume."""
    words = re.findall(r"[A-Za-z][A-Za-z+#.\-]{2,}", job_description)
    counts = Counter(
        w.lower().rstrip(".-") for w in words if w.lower() not in _STOPWORDS
    )
    resume_lower = resume.lower()
    missing = [
        (term, n) for term, n in counts.most_common(60)
        if n >= 2 and term not in resume_lower
    ]
    return [t for t, _ in missing[:top_n]]


def run_tailor(title: str, company: str, description: str) -> str:
    """Blocking; call via asyncio.to_thread. Returns the tailor pack markdown."""
    resume = read_master_resume()
    llm = make_llm(temperature=0.4)
    description = description[:2500]
    resume_excerpt = resume[:3000]

    honesty_rule = (
        "HARD RULE: use ONLY facts present in the MASTER RESUME. Select and "
        "rephrase — NEVER invent employers, projects, metrics, or skills "
        "that are not listed. If the resume lacks something the job wants, "
        "omit it rather than fabricate."
    )

    bullets = call_text(llm, (
        f"You are an expert resume writer. {honesty_rule}\n\n"
        f"# JOB POSTING ({title} at {company})\n{description}\n\n"
        f"# MASTER RESUME\n{resume_excerpt}\n\n"
        "Write 5-7 resume bullets tailored to this posting: lead with the "
        "posting's own vocabulary, quantify where the resume provides numbers, "
        "strongest matches first. Output ONLY a markdown bullet list."
    ))

    letter = call_text(llm, (
        f"You are an expert cover-letter writer. {honesty_rule}\n\n"
        f"# JOB POSTING ({title} at {company})\n{description}\n\n"
        f"# MASTER RESUME\n{resume_excerpt}\n\n"
        "Write a 3-paragraph cover letter (under 250 words): (1) why this "
        "specific role/company, (2) the two strongest matching qualifications "
        "with evidence from the resume, (3) confident close. Professional but "
        "human tone; no clichés like 'I am writing to express'. Output ONLY "
        "the letter body in markdown."
    ))

    gaps = keyword_gap(description, resume)
    gap_section = (
        "\n".join(
            f"- `{g}` — appears in the posting but not in your master resume; "
            "add it if you can honestly claim it, or prepare to address it"
            for g in gaps
        )
        if gaps
        else "- No significant gaps detected — strong keyword coverage."
    )

    return "\n".join([
        f"# Tailor Pack: {title} @ {company}",
        "",
        "## Tailored Resume Bullets",
        "",
        bullets,
        "",
        "## Cover Letter Draft",
        "",
        letter,
        "",
        "## Keyword Gap Analysis *(deterministic)*",
        "",
        gap_section,
        "",
        "---",
        "*Generated locally from `profile/master_resume.md` — verify every "
        "line before sending; the agent selects from your resume but you own "
        "the truth of it.*",
    ])
