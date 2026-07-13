"""Regex Kill Switch (P3.1) — cheap deterministic filter before any embedding.

Rules live in filter_rules.yaml so tuning never requires a code change.
"""

import logging
import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.models.job import Job

logger = logging.getLogger("synapse.filtering")

RULES_PATH = Path(__file__).parents[1] / "filter_rules.yaml"


@lru_cache(maxsize=1)
def _load_rules() -> dict[str, list[re.Pattern]]:
    raw = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
    return {
        key: [re.compile(p, re.IGNORECASE) for p in (raw.get(key) or [])]
        for key in ("include", "exclude", "exclude_title_only")
    }


def reload_rules() -> None:
    """Clear the cache after editing filter_rules.yaml."""
    _load_rules.cache_clear()


def kill_switch(job: Job) -> tuple[bool, str]:
    """Return (passed, reason). reason is '' when passed."""
    rules = _load_rules()
    haystack = f"{job.title}\n{job.description_markdown}"

    for pattern in rules["exclude_title_only"]:
        if pattern.search(job.title):
            return False, f"title matched exclude: {pattern.pattern}"

    for pattern in rules["exclude"]:
        if pattern.search(haystack):
            return False, f"matched exclude: {pattern.pattern}"

    if rules["include"] and not any(p.search(haystack) for p in rules["include"]):
        return False, "no include pattern matched"

    return True, ""
