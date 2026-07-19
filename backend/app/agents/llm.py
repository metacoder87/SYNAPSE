"""Shared local-LLM helpers for all agent pipelines.

Everything routes to LOCAL Ollama via its OpenAI-compatible endpoint
(localhost:11434/v1). No cloud services.
"""

import json
import logging
import re

from app.config import settings

logger = logging.getLogger("synapse.agents.llm")

JSON_RETRIES = 2


def make_llm(temperature: float, model: str | None = None):
    from crewai import LLM

    return LLM(
        model=f"ollama/{model or settings.ollama_model}",
        base_url=settings.ollama_base_url,
        temperature=temperature,
    )


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response."""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unbalanced JSON in response")


def call_json(llm, prompt: str, retries: int = JSON_RETRIES) -> dict:
    last_err = "unknown"
    for attempt in range(retries + 1):
        raw = llm.call(prompt if attempt == 0 else (
            f"{prompt}\n\nYour previous reply was invalid ({last_err}). "
            "Respond with ONLY a valid JSON object, no prose, no code fences."
        ))
        try:
            return extract_json(str(raw))
        except (ValueError, json.JSONDecodeError) as exc:
            last_err = str(exc)[:100]
            logger.warning("JSON parse retry %d/%d: %s", attempt + 1, retries, last_err)
    raise ValueError(f"LLM never produced valid JSON: {last_err}")


def call_text(llm, prompt: str) -> str:
    """Plain markdown/text generation."""
    return str(llm.call(prompt)).strip()
