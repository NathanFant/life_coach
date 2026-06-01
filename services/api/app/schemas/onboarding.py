"""
Pydantic schemas for the onboarding API.

These are the source of truth for the OpenAPI document that generates
@repo/api-client and @repo/types in the TypeScript packages.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OnboardingStateResponse(BaseModel):
    """Returned by GET /v1/onboarding and after each answer."""

    is_complete: bool
    completeness: float = Field(ge=0.0, le=1.0)
    next_question: QuestionOut | None = None
    filled_slots: dict[str, Any] = Field(default_factory=dict)


class QuestionOut(BaseModel):
    slot: str
    text: str
    hint: str = ""


class AnswerIn(BaseModel):
    slot: str = Field(description="The DomainSlot key being answered")
    raw_answer: str = Field(description="The user's free-text answer")
    structured_value: Any = Field(
        default=None,
        description="Optional pre-structured value; skips LLM parsing if provided",
    )


class OnboardingCompleteResponse(BaseModel):
    """Returned by POST /v1/onboarding/complete."""

    life_profile_id: str
    completeness: float
    seeded_goals: int = 0
    seeded_projects: int = 0
