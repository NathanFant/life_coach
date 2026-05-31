"""CoachLLM — the model-agnostic LLM façade (docs/DESIGN.md §6.1).

The ONLY module that knows about providers. Everything else depends on this
interface, so OpenAI / Anthropic / Gemini are config, not code. Wraps LiteLLM
for routing + fallback, and is the choke point for PII redaction (§7.6) and
Langfuse tracing.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMMessage:
    role: str  # system | user | assistant | tool
    content: str


class CoachLLM:
    """Provider-agnostic generation, streaming, tools, and embeddings."""

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Single completion (optionally tool/structured-output constrained)."""
        raise NotImplementedError

    async def stream(
        self, messages: list[LLMMessage], *, model: str | None = None
    ) -> AsyncIterator[str]:
        """Token stream for live coaching turns."""
        raise NotImplementedError
        yield  # pragma: no cover  (makes this an async generator)

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        """Embed text(s) for the unified vector index (§5.1)."""
        raise NotImplementedError
