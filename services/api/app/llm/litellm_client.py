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

# Errors worth retrying (transient) — will retry within the same provider
_RETRYABLE = (
    litellm.exceptions.RateLimitError,
    litellm.exceptions.ServiceUnavailableError,
    litellm.exceptions.Timeout,
)

# Errors that indicate the provider is unavailable — trigger fallback
_FALLBACK_ERRORS = (
    litellm.exceptions.AuthenticationError,
    litellm.exceptions.BadRequestError,
    litellm.exceptions.APIError,
)

# Fallback chains: if primary provider fails, try these in order
_FALLBACK_CHAINS: dict[str, list[str]] = {
    # Coaching: Anthropic → OpenAI → Gemini
    "anthropic/claude-sonnet-4-6": [
        "openai/gpt-4o",
        "gemini/gemini-2.0-flash",
    ],
    # Extraction (cheap): Anthropic Haiku → OpenAI mini → Gemini flash
    "anthropic/claude-haiku-4-5-20251001": [
        "openai/gpt-4o-mini",
        "gemini/gemini-1.5-flash",
    ],
    # Embedding: OpenAI → Anthropic (less ideal but works)
    "openai/text-embedding-3-small": [
        "openai/text-embedding-3-large",
    ],
}


class LiteLLMCoachLLM(CoachLLM):
    """
    CoachLLM backed by LiteLLM with provider fallback.

    model: the default model string used when callers don't override.
    Falls back to alternate providers if the primary one is unavailable.
    """

    def __init__(self, model: str) -> None:
        self._default_model = model
        self._fallbacks = _FALLBACK_CHAINS.get(model, [])

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
        fallbacks = _FALLBACK_CHAINS.get(m, [])
        models_to_try = [m] + fallbacks

        last_error = None
        for attempt_model in models_to_try:
            try:
                kwargs: dict[str, Any] = {
                    "model": attempt_model,
                    "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
                }
                if tools:
                    kwargs["tools"] = tools
                if response_format:
                    kwargs["response_format"] = response_format

                resp = await litellm.acompletion(**kwargs)
                choice = resp.choices[0]
                result = LLMResponse(
                    content=choice.message.content or "",
                    tool_calls=choice.message.tool_calls or [],
                    model=resp.model or attempt_model,
                    usage={
                        "prompt_tokens": resp.usage.prompt_tokens,
                        "completion_tokens": resp.usage.completion_tokens,
                    },
                    raw=resp,
                )
                if attempt_model != m:
                    logger.info(
                        "llm.fallback_success",
                        primary=m,
                        fallback=attempt_model,
                    )
                return result
            except _FALLBACK_ERRORS as e:
                last_error = e
                logger.warning(
                    "llm.fallback_needed",
                    model=attempt_model,
                    error=type(e).__name__,
                    next_model=fallbacks[models_to_try.index(attempt_model) + 1] if models_to_try.index(attempt_model) + 1 < len(fallbacks) else "none",
                )
                continue
            except Exception:
                raise

        if last_error:
            logger.error("llm.all_fallbacks_exhausted", primary=m, error=str(last_error))
            raise last_error
        raise RuntimeError(f"No LLM providers available for {m}")

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        m = model or self._default_model
        fallbacks = _FALLBACK_CHAINS.get(m, [])
        models_to_try = [m] + fallbacks

        last_error = None
        for attempt_model in models_to_try:
            try:
                resp = await litellm.acompletion(
                    model=attempt_model,
                    messages=[{"role": msg.role, "content": msg.content} for msg in messages],
                    stream=True,
                )
                async for chunk in resp:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                if attempt_model != m:
                    logger.info("llm.stream_fallback_success", primary=m, fallback=attempt_model)
                return
            except _FALLBACK_ERRORS as e:
                last_error = e
                logger.warning("llm.stream_fallback_needed", model=attempt_model, error=type(e).__name__)
                continue
            except Exception:
                raise

        if last_error:
            raise last_error
        raise RuntimeError(f"No LLM providers available for streaming with {m}")

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        m = model or self._default_model
        fallbacks = _FALLBACK_CHAINS.get(m, [])
        models_to_try = [m] + fallbacks

        last_error = None
        for attempt_model in models_to_try:
            try:
                resp = await litellm.aembedding(model=attempt_model, input=texts)
                if attempt_model != m:
                    logger.info("llm.embed_fallback_success", primary=m, fallback=attempt_model)
                return [item.embedding for item in resp.data]
            except _FALLBACK_ERRORS as e:
                last_error = e
                logger.warning("llm.embed_fallback_needed", model=attempt_model, error=type(e).__name__)
                continue
            except Exception:
                raise

        if last_error:
            raise last_error
        raise RuntimeError(f"No LLM providers available for embeddings with {m}")
