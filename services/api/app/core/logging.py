"""
Structured logging setup using structlog.

Configures structlog to emit JSON in production and human-friendly coloured
output in development.  Call configure_logging() once at application startup
(in app/main.py) before any other code runs.

Usage:
    import structlog
    logger = structlog.get_logger(__name__)
    logger.info("memory.retrieved", user_id=str(user_id), count=5, latency_ms=12)

Langfuse tracing for LLM calls is configured separately in app/core/tracing.py.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """
    Configure structlog and the stdlib logging root.

    Must be called once at startup before any loggers are created.
    Safe to call multiple times (structlog guards against double-config).
    """
    settings = get_settings()
    is_dev = settings.environment in ("development", "test")

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if is_dev:
        # Coloured, human-readable output for local dev
        processors: list[structlog.types.Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Machine-readable JSON for log aggregators (CloudWatch, Datadog, etc.)
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure the stdlib root logger so third-party libs use the same level
    logging.basicConfig(
        level=settings.log_level.upper(),
        stream=sys.stdout,
        format="%(message)s",  # structlog renders the full line
    )
