"""
LiteLLMCoachLLM — the production CoachLLM implementation.

Wraps LiteLLM to provide:
  - Unified OpenAI / Anthropic / Gemini interface
  - Automatic retries on transient errors (429, 503) via tenacity
  - Streaming support (async generator)
  - Embeddings
  - Langfuse tracing (when configured)
  - PII-safe logging (content is never logged at DEBUG)

The model string format follows LiteLLM conventions:
  "anthropic/claude-sonnet-4-6"
  "openai/gpt-4o-mini"
  "gemini/gemini-1.5-flash"

See docs/DESIGN.md §6.1 for the routing and fallback design.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import litellm
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.llm.coach_llm import CoachLLM, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)

# Errors worth retrying (transient)
_RETRYABLE = (
    litellm.exceptions.RateLimitError,
    litellm.exceptions.ServiceUnavailableError,
    litellm.exceptions.Timeout,
)


class LiteLLMCoachLLM(CoachLLM):
    """
    CoachLLM backed by LiteLLM.

    model: the default model string used when callers don't override.
    """

    def __init__(self, model: str) -> None:
        self._default_model = model

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        m = model or self._default_model
        kwargs: dict[str, Any] = {
            "model": m,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
        }
        if tools:
            kwargs["tools"] = tools
        if response_format:
            kwargs["response_format"] = response_format

        resp = await litellm.acompletion(**kwargs)
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=choice.message.tool_calls or [],
            model=resp.model or m,
            usage={
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            },
            raw=resp,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        m = model or self._default_model
        resp = await litellm.acompletion(
            model=m,
            messages=[{"role": msg.role, "content": msg.content} for msg in messages],
            stream=True,
        )
        async for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        m = model or self._default_model
        resp = await litellm.aembedding(model=m, input=texts)
        return [item.embedding for item in resp.data]
