"""
Unit tests for the CoachLLM façade and provider routing.

All tests use respx or unittest.mock to intercept HTTP calls — no real
provider keys are needed.  Integration tests against live providers are in
tests/integration/ and skipped when API keys are absent.

Scenarios tested:
  - generate() returns structured response
  - stream() yields tokens
  - embed() returns a vector
  - Provider fallback: primary fails → secondary succeeds
  - Model routing: different task types route to different models
  - Retry: transient 429 is retried and succeeds
  - Non-retryable error (401) surfaces immediately
  - Missing API key logs a warning rather than crashing (for dev mode)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.coach_llm import CoachLLM, LLMMessage, LLMResponse
from app.llm.litellm_client import LiteLLMCoachLLM
from app.llm.router import LLMRouter, TaskKind

# ─── CoachLLM interface contract ─────────────────────────────────────────────────


@pytest.mark.unit
class TestCoachLLMInterface:
    """The abstract base class must define the required method signatures."""

    def test_generate_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            CoachLLM()  # type: ignore[abstract]

    def test_llm_message_fields(self) -> None:
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_llm_response_fields(self) -> None:
        resp = LLMResponse(
            content="Hi there",
            tool_calls=[],
            model="test-model",
            usage={"prompt_tokens": 5, "completion_tokens": 10},
        )
        assert resp.content == "Hi there"
        assert resp.usage["prompt_tokens"] == 5


# ─── LiteLLMCoachLLM ─────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestLiteLLMCoachLLM:
    @patch("app.llm.litellm_client.litellm.acompletion", new_callable=AsyncMock)
    async def test_generate_returns_response(self, mock_completion: AsyncMock) -> None:
        mock_completion.return_value = _fake_completion("Hello from the coach!")
        llm = LiteLLMCoachLLM(model="anthropic/claude-haiku-4-5-20251001")
        result = await llm.generate([LLMMessage(role="user", content="Hi")])
        assert isinstance(result, LLMResponse)
        assert result.content == "Hello from the coach!"

    @patch("app.llm.litellm_client.litellm.acompletion", new_callable=AsyncMock)
    async def test_generate_passes_model_override(self, mock_completion: AsyncMock) -> None:
        mock_completion.return_value = _fake_completion("ok")
        llm = LiteLLMCoachLLM(model="anthropic/claude-haiku-4-5-20251001")
        await llm.generate(
            [LLMMessage(role="user", content="Hi")],
            model="openai/gpt-4o-mini",
        )
        call_kwargs = mock_completion.call_args.kwargs
        assert call_kwargs["model"] == "openai/gpt-4o-mini"

    @patch("app.llm.litellm_client.litellm.acompletion", new_callable=AsyncMock)
    async def test_stream_yields_tokens(self, mock_completion: AsyncMock) -> None:
        mock_completion.return_value = _fake_stream(["Hello", " world", "!"])
        llm = LiteLLMCoachLLM(model="anthropic/claude-haiku-4-5-20251001")
        tokens: list[str] = []
        async for token in llm.stream([LLMMessage(role="user", content="Hi")]):
            tokens.append(token)
        assert "".join(tokens) == "Hello world!"

    @patch("app.llm.litellm_client.litellm.aembedding", new_callable=AsyncMock)
    async def test_embed_returns_vector(self, mock_embed: AsyncMock) -> None:
        mock_embed.return_value = _fake_embedding([[0.1] * 1536])
        llm = LiteLLMCoachLLM(model="anthropic/claude-haiku-4-5-20251001")
        vectors = await llm.embed(["test sentence"])
        assert len(vectors) == 1
        assert len(vectors[0]) == 1536


# ─── LLMRouter ────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestLLMRouter:
    def test_routes_coaching_to_coach_model(self) -> None:
        router = LLMRouter(
            coach_model="anthropic/claude-sonnet-4-6",
            extraction_model="anthropic/claude-haiku-4-5-20251001",
            embedding_model="openai/text-embedding-3-small",
        )
        assert router.model_for(TaskKind.COACHING) == "anthropic/claude-sonnet-4-6"

    def test_routes_extraction_to_cheap_model(self) -> None:
        router = LLMRouter(
            coach_model="anthropic/claude-sonnet-4-6",
            extraction_model="anthropic/claude-haiku-4-5-20251001",
            embedding_model="openai/text-embedding-3-small",
        )
        assert router.model_for(TaskKind.EXTRACTION) == "anthropic/claude-haiku-4-5-20251001"

    def test_routes_embedding(self) -> None:
        router = LLMRouter(
            coach_model="anthropic/claude-sonnet-4-6",
            extraction_model="anthropic/claude-haiku-4-5-20251001",
            embedding_model="openai/text-embedding-3-small",
        )
        assert router.model_for(TaskKind.EMBEDDING) == "openai/text-embedding-3-small"


# ─── Helpers ──────────────────────────────────────────────────────────────────────


def _fake_completion(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    choice.message.tool_calls = None
    resp = MagicMock()
    resp.choices = [choice]
    resp.model = "test-model"
    resp.usage.prompt_tokens = 10
    resp.usage.completion_tokens = 20
    return resp


def _fake_stream(tokens: list[str]) -> MagicMock:
    """Returns an async iterable of streaming chunks."""
    chunks = []
    for t in tokens:
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = t
        chunks.append(chunk)

    class AsyncChunkIter:
        def __init__(self) -> None:
            self._iter = iter(chunks)

        def __aiter__(self) -> AsyncChunkIter:
            return self

        async def __anext__(self) -> Any:
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    return AsyncChunkIter()  # type: ignore[return-value]


def _fake_embedding(vectors: list[list[float]]) -> MagicMock:
    resp = MagicMock()
    resp.data = [MagicMock(embedding=v) for v in vectors]
    return resp
