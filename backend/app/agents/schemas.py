"""Structured claim/verdict models for the deep-research pipeline (R2)."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

PROMPT_VERSION = "2.0"

SCOUT_SECTIONS = ("company_overview", "ai_maturity", "remote_culture", "red_flags")
NETWORKER_SECTIONS = ("hiring_owner", "why_open", "outreach_angles")

SECTION_TITLES = {
    "company_overview": "Company Overview",
    "ai_maturity": "AI Maturity Signals",
    "remote_culture": "Remote Culture & Benefits",
    "red_flags": "Red Flags",
    "hiring_owner": "Likely Hiring Owner",
    "why_open": "Why This Role Is Open",
    "outreach_angles": "Outreach Angles",
}

JOB_SOURCE_ID = "JOB"  # special evidence id: the job posting itself


class Claim(BaseModel):
    text: str = Field(min_length=5)
    evidence_ids: list[str] = Field(default_factory=list)
    section: str

    @field_validator("evidence_ids")
    @classmethod
    def normalize_ids(cls, v: list[str]) -> list[str]:
        return [e.strip().upper() for e in v if e and e.strip()]

    @field_validator("text")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class ClaimSet(BaseModel):
    claims: list[Claim]

    def for_section(self, section: str) -> list["Claim"]:
        return [c for c in self.claims if c.section == section]


class Verdict(BaseModel):
    verdict: Literal["supported", "contradicted", "insufficient"]
    rationale: str = ""


class DeepDiveResult(BaseModel):
    markdown: str
    evidence: list[dict]
    verdicts: list[dict]
    prompt_version: str = PROMPT_VERSION
    citation_coverage: float = 0.0
    verified_ratio: float = 0.0
