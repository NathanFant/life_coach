"""Pydantic schemas for the life profile and domain endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import UUID4, BaseModel, Field


class DomainOut(BaseModel):
    id: UUID4
    kind: str
    current_state: str | None = None
    desired_1y: str | None = None
    desired_5y: str | None = None
    obstacles: list[Any] = Field(default_factory=list)
    strengths: list[Any] = Field(default_factory=list)
    priority: int = 0


class LifeProfileOut(BaseModel):
    id: UUID4
    life_stage: str | None = None
    summary: str | None = None
    completeness: float
    attributes: dict[str, Any] = Field(default_factory=dict)
    domains: list[DomainOut] = Field(default_factory=list)


class ProfilePatchIn(BaseModel):
    life_stage: str | None = None
    summary: str | None = None
    attributes: dict[str, Any] | None = None
