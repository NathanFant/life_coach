"""
Root pytest configuration and shared fixtures for the life-coach API test suite.

Test layers (see pyproject.toml [tool.pytest.ini_options] markers):
  unit        — no external services; runs in CI always
  integration — requires Postgres + Redis (docker-compose up -d)
  eval        — coaching quality rubrics; slow, curated dataset
  safety      — red-team regression suite; CI gate before deploy

All async tests use asyncio via pytest-asyncio (asyncio_mode = "auto").
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ─── Event loop ────────────────────────────────────────────────────────────────

# ─── HTTP client ───────────────────────────────────────────────────────────────


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Sync ASGI test client for endpoint tests that don't need async."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ─── Fake JWT / auth ───────────────────────────────────────────────────────────

FAKE_USER_ID = "user_01HTEST000000000000000000"
FAKE_USER_EMAIL = "test@example.com"
FAKE_INTERNAL_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def fake_user_payload() -> dict[str, Any]:
    """A minimal decoded Clerk JWT payload for mocking auth."""
    return {
        "sub": FAKE_USER_ID,
        "email": FAKE_USER_EMAIL,
        "email_verified": True,
        "iss": "https://test.clerk.accounts.dev",
        "aud": "life-coach",
        "exp": 9999999999,
        "iat": 1000000000,
    }


# ─── LLM mock ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm() -> MagicMock:
    """A mock CoachLLM that returns canned responses without hitting providers."""
    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value={
            "content": "This is a test coaching response.",
            "tool_calls": [],
            "model": "test-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
    )
    llm.stream = AsyncMock()
    llm.embed = AsyncMock(return_value=[[0.1] * 1536])
    return llm


# ─── Environment guard ─────────────────────────────────────────────────────────


def pytest_configure(config: pytest.Config) -> None:
    """Ensure tests never accidentally hit production services."""
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+psycopg://coach:coach@localhost:5432/lifecoach_test"
    )
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
    os.environ.setdefault("CLERK_JWKS_URL", "https://test.clerk.accounts.dev/.well-known/jwks.json")
    os.environ.setdefault("CLERK_ISSUER", "https://test.clerk.accounts.dev")
