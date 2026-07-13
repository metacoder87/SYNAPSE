"""Arize Phoenix tracing for the CrewAI pipeline (P7.3).

Traces every agent step and LLM call (via LiteLLM) to the local Phoenix
container — browse at http://localhost:6006. Fails soft: if Phoenix or the
instrumentation packages are missing, the app runs untraced.
"""

import logging

from app.config import settings

logger = logging.getLogger("synapse.tracing")

_initialized = False


def init_tracing() -> bool:
    global _initialized
    if _initialized or not settings.phoenix_enabled:
        return _initialized
    try:
        from phoenix.otel import register

        tracer_provider = register(
            project_name="synapse",
            endpoint=settings.phoenix_endpoint,
            batch=True,
        )

        from openinference.instrumentation.crewai import CrewAIInstrumentor
        from openinference.instrumentation.litellm import LiteLLMInstrumentor

        CrewAIInstrumentor().instrument(tracer_provider=tracer_provider)
        LiteLLMInstrumentor().instrument(tracer_provider=tracer_provider)

        _initialized = True
        logger.info("Phoenix tracing active → %s", settings.phoenix_endpoint)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phoenix tracing disabled: %s", str(exc)[:200])
    return _initialized
