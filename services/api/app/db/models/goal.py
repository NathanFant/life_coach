"""
Goal, Project, Milestone, and Task models.

These form the progress-tracking backbone of the life model:
  Goal (what the user wants) → Project (ongoing initiative) → Milestone → Task

Hierarchy is optional — tasks can be attached directly to goals, or be standalone
coaching actions. See docs/DESIGN.md §2.2 and §4.3.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Goal(Base, TimestampMixin):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("domains.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # short | long
    horizon: Mapped[str] = mapped_column(Text, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # active | achieved | paused | dropped
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    # 0..1 progress fraction
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 1..5 importance (user-editable + AI-suggested)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # ─── Relationships ───────────────────────────────────────────────────────
    projects: Mapped[list[Project]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_goals_user_status_importance", "user_id", "status", "importance"),)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # startup | side-business | certification | fitness | …
    kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    # active | paused | completed | abandoned
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    # on_track | at_risk | stalled
    health: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Flexible project metadata (revenue, runway, team size, etc.)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'")
    )

    # ─── Relationships ───────────────────────────────────────────────────────
    goal: Mapped[Goal | None] = relationship(back_populates="projects")
    milestones: Mapped[list[Milestone]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_projects_user_status", "user_id", "status"),)


class Milestone(Base, TimestampMixin):
    __tablename__ = "milestones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # pending | achieved | dropped
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ─── Relationships ───────────────────────────────────────────────────────
    project: Mapped[Project] = relationship(back_populates="milestones")
    tasks: Mapped[list[Task]] = relationship(
        back_populates="milestone", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_milestones_project_id", "project_id"),
        Index("ix_milestones_user_id", "user_id"),
    )


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    milestone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("milestones.id", ondelete="CASCADE"), nullable=True
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # todo | doing | done | dropped
    status: Mapped[str] = mapped_column(Text, nullable=False, default="todo")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # coach | user — who created this task
    source: Mapped[str] = mapped_column(Text, nullable=False, default="coach")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ─── Relationships ───────────────────────────────────────────────────────
    milestone: Mapped[Milestone | None] = relationship(back_populates="tasks")

    __table_args__ = (
        Index("ix_tasks_user_status", "user_id", "status"),
        Index("ix_tasks_milestone_id", "milestone_id"),
    )
