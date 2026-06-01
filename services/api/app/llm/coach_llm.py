"""
CoachLLM — the model-agnostic LLM façade (docs/DESIGN.md §6.1).

The ONLY module that knows about providers.  Everything else depends on this
abstract interface so OpenAI / Anthropic / Gemini are config, not code.

Public types:
  LLMMessage  — a single conversation turn
  LLMResponse — a complete (non-streaming) response
  CoachLLM    — abstract base; implement generate(), stream(), embed()

Implementations live in:
  app.llm.litellm_client  — production (LiteLLM wrapper)
  tests/*                 — in-test mocks via unittest.mock
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMMessage:
    """A single turn in a conversation."""

    role: str  # system | user | assistant | tool
    content: str


@dataclass
class LLMResponse:
    """The result of a non-streaming completion."""

    content: str
    tool_calls: list[Any]
    model: str
    usage: dict[str, int]
    raw: Any = field(default=None, repr=False)  # provider response, for debugging


class CoachLLM(ABC):
    """
    Provider-agnostic interface for generation, streaming, tools, and embeddings.

    All production code depends on this type, never on LiteLLM or provider SDKs
    directly — keeping providers behind this seam means routing, fallback, and
    PII-redaction logic is centralised in one place.
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Single-shot completion (optionally tool/structured-output constrained)."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """Token stream for live coaching turns."""
        ...

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        """Embed text(s) for the unified vector index (docs/DESIGN.md §5.1)."""
        ...
