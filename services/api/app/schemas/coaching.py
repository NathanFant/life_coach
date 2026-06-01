"""Pydantic schemas for coaching sessions and SSE events."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import UUID4, BaseModel


class MessageIn(BaseModel):
    content: str


class SessionOut(BaseModel):
    id: UUID4
    focus_domain: str | None = None
    summary: str | None = None
    detected_changes: list[Any]
    outcome_actions: list[Any]


# ─── SSE event envelope ──────────────────────────────────────────────────────────
# Each SSE event is a JSON payload of one of these types (docs/DESIGN.md §9.3).


class TokenEvent(BaseModel):
    event: Literal["token"] = "token"
    data: str


class ToolCallEvent(BaseModel):
    event: Literal["tool_call"] = "tool_call"
    name: str
    payload: dict[str, Any]


class FollowupsEvent(BaseModel):
    event: Literal["followups"] = "followups"
    questions: list[str]


class ChangeDetectedEvent(BaseModel):
    event: Literal["change_detected"] = "change_detected"
    change_type: str
    confidence: float


class SafetyEvent(BaseModel):
    event: Literal["safety"] = "safety"
    category: str
    resources: list[dict[str, str]] = []


class DoneEvent(BaseModel):
    event: Literal["done"] = "done"
    session_id: str
    tokens_used: int = 0
