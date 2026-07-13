"""P3.1 — Regex Kill Switch mock-payload matrix (PRD §8)."""

from app.filtering import kill_switch
from tests.conftest import make_job


def _check(title: str, description: str = "Design enterprise AI architecture.") -> tuple:
    return kill_switch(make_job(title=title, description_markdown=description))


def test_target_role_passes():
    passed, reason = _check("Corporate AI Architect")
    assert passed, reason


def test_strategic_ai_leadership_passes():
    passed, reason = _check(
        "Director of Machine Learning", "Own the enterprise AI platform strategy."
    )
    assert passed, reason


def test_junior_title_killed():
    passed, reason = _check("Junior AI Architect")
    assert not passed
    assert "exclude" in reason


def test_intern_killed():
    passed, _ = _check("AI Architecture Intern")
    assert not passed


def test_onsite_only_killed():
    passed, reason = _check("Principal AI Architect", "Great role but on-site only in Tulsa.")
    assert not passed


def test_irrelevant_role_killed_by_include():
    passed, reason = _check("Retail Store Manager", "Manage a busy storefront.")
    assert not passed
    assert reason == "no include pattern matched"


def test_description_mention_does_not_kill():
    """'junior' in the description (e.g. 'mentor junior staff') must not kill."""
    passed, reason = _check(
        "Principal AI Architect", "You will mentor junior engineers and set AI strategy."
    )
    assert passed, reason
