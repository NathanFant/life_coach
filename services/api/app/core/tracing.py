"""
Langfuse LLM tracing setup (docs/DESIGN.md §6.6).

Provides a thin wrapper around the Langfuse SDK that:
  - Is a no-op when LANGFUSE_PUBLIC_KEY is absent (local dev without Langfuse)
  - Attaches traces to LLM calls made through CoachLLM
  - Tags every trace with user_id, task_kind, and model

Usage:
    from app.core.tracing import get_tracer
    tracer = get_tracer()
    with tracer.span("coaching.turn", user_id=user_id, task="coaching") as span:
        result = await llm.generate(messages)
        span.update(model=result.model, tokens=result.usage)

Note: Langfuse also integrates directly with LiteLLM via the LiteLLM callback;
that is configured in app/llm/litellm_client.py when keys are present.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any


class _NoopSpan:
    """Returned when Langfuse is not configured — all operations are no-ops."""

    def update(self, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> _NoopSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _NoopTracer:
    @contextmanager
    def span(self, name: str, **kwargs: Any) -> Generator[_NoopSpan, None, None]:
        yield _NoopSpan()

    def flush(self) -> None:
        pass


class LangfuseTracer:
    """Live tracer that records to Langfuse."""

    def __init__(self) -> None:
        from langfuse import Langfuse

        self._client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )

    @contextmanager
    def span(self, name: str, **kwargs: Any) -> Generator[Any, None, None]:
        trace = self._client.trace(name=name, metadata=kwargs)
        yield trace
        trace.update(output="done")

    def flush(self) -> None:
        self._client.flush()


# Module-level singleton
_tracer: LangfuseTracer | _NoopTracer | None = None


def get_tracer() -> LangfuseTracer | _NoopTracer:
    global _tracer
    if _tracer is None:
        _tracer = LangfuseTracer() if os.environ.get("LANGFUSE_PUBLIC_KEY") else _NoopTracer()
    return _tracer


def configure_langfuse_litellm_callback() -> None:
    """
    Register the Langfuse success/failure callbacks with LiteLLM so every
    completion call is automatically traced.

    Called at app startup when keys are present.
    """
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        return
    try:
        import litellm
        from langfuse.callback import CallbackHandler

        handler = CallbackHandler(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        litellm.success_callback = [handler]
        litellm.failure_callback = [handler]
    except ImportError:
        pass  # Langfuse not installed — tracing disabled
