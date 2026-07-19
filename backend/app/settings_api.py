"""E5: settings endpoints — edit config files from the UI, with validation
and hot-reload. Files stay the source of truth (template-friendly)."""

import asyncio
import logging
import re

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.filtering import RULES_PATH, reload_rules
from app.matching import PROFILE_PATH
from app.agents.tailor import RESUME_PATH

logger = logging.getLogger("synapse.settings")

router = APIRouter(prefix="/settings")

FILES = {
    "profile": PROFILE_PATH,
    "resume": RESUME_PATH,
    "filters": RULES_PATH,
}


class FileContent(BaseModel):
    content: str


def validate_filter_rules(content: str) -> str | None:
    """Return an error message, or None if valid."""
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return f"invalid YAML: {str(exc)[:200]}"
    if not isinstance(data, dict):
        return "rules file must be a YAML mapping"
    for key in ("include", "exclude", "exclude_title_only"):
        patterns = data.get(key) or []
        if not isinstance(patterns, list):
            return f"'{key}' must be a list"
        for p in patterns:
            try:
                re.compile(p, re.IGNORECASE)
            except re.error as exc:
                return f"invalid regex in '{key}': {p!r} — {exc}"
    return None


@router.get("/files/{name}")
async def get_file(name: str) -> dict:
    path = FILES.get(name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"unknown file: {name}")
    try:
        return {"name": name, "content": path.read_text(encoding="utf-8")}
    except FileNotFoundError:
        return {"name": name, "content": ""}


@router.put("/files/{name}")
async def put_file(name: str, body: FileContent) -> dict:
    path = FILES.get(name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"unknown file: {name}")
    if not body.content.strip():
        raise HTTPException(status_code=422, detail="content cannot be empty")

    if name == "filters":
        error = validate_filter_rules(body.content)
        if error:
            raise HTTPException(status_code=422, detail=error)

    path.write_text(body.content, encoding="utf-8")
    applied = "saved"

    if name == "filters":
        reload_rules()
        applied = "saved + rules reloaded"
    elif name == "profile":
        from app import matching

        try:
            await asyncio.to_thread(matching.refresh_profile)
            applied = "saved + profile re-embedded"
        except Exception as exc:  # noqa: BLE001
            logger.warning("profile re-embed failed: %s", str(exc)[:150])
            applied = "saved (re-embed failed — is Chroma up?)"

    logger.info("settings: %s %s", name, applied)
    return {"name": name, "status": applied}
