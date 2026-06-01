"""Pydantic schemas for goals, projects, milestones, and tasks."""

from __future__ import annotations

from datetime import date

from pydantic import UUID4, BaseModel, Field


class GoalOut(BaseModel):
    id: UUID4
    title: str
    description: str | None = None
    horizon: str
    status: str
    progress: float
    importance: int
    target_date: date | None = None
    domain_id: UUID4 | None = None


class GoalCreateIn(BaseModel):
    title: str
    horizon: str = Field(pattern="^(short|long)$")
    description: str | None = None
    target_date: date | None = None
    importance: int = Field(default=3, ge=1, le=5)
    domain_id: UUID4 | None = None


class GoalPatchIn(BaseModel):
    title: str | None = None
    status: str | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    importance: int | None = Field(default=None, ge=1, le=5)
    target_date: date | None = None


class ProjectOut(BaseModel):
    id: UUID4
    title: str
    kind: str | None = None
    status: str
    health: str | None = None
    goal_id: UUID4 | None = None


class TaskOut(BaseModel):
    id: UUID4
    title: str
    status: str
    source: str
    due_date: date | None = None
    milestone_id: UUID4 | None = None
    goal_id: UUID4 | None = None


class TaskCreateIn(BaseModel):
    title: str
    due_date: date | None = None
    milestone_id: UUID4 | None = None
    goal_id: UUID4 | None = None
    source: str = "user"
