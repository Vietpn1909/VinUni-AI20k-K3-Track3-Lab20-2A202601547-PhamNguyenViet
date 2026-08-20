"""Tracing hooks.

Supports two modes:
- LangSmith: if LANGSMITH_API_KEY is set, auto-configures environment for tracing.
- Local: minimal span context manager that logs duration to Python logging.

LangGraph automatically emits traces to LangSmith when the env vars are set,
so we only need to configure the environment once at startup.
"""

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from multi_agent_research_lab.core.config import get_settings

logger = logging.getLogger(__name__)


def configure_tracing() -> None:
    """Set up tracing providers based on available API keys.

    Call this once at startup (e.g., from CLI _init).
    """
    settings = get_settings()

    # --- LangSmith auto-tracing ---
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        logger.info(
            "LangSmith tracing enabled (project=%s)",
            settings.langsmith_project,
        )
    else:
        logger.info(
            "LangSmith not configured. Set LANGSMITH_API_KEY for "
            "remote tracing."
        )

    # --- Langfuse (optional) ---
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host
        logger.info("Langfuse tracing configured (host=%s)", settings.langfuse_host)


@contextmanager
def trace_span(
    name: str, attributes: dict[str, Any] | None = None
) -> Iterator[dict[str, Any]]:
    """Local span context manager with duration tracking.

    Always logs span start/end to Python logger. Works alongside
    LangSmith/Langfuse which trace LangGraph invocations automatically.
    """
    started = perf_counter()
    span: dict[str, Any] = {
        "name": name,
        "attributes": attributes or {},
        "duration_seconds": None,
    }
    logger.debug("Span START: %s %s", name, attributes or "")
    try:
        yield span
    finally:
        duration = perf_counter() - started
        span["duration_seconds"] = duration
        logger.info("Span END: %s (%.3fs)", name, duration)

