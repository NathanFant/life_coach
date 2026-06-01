"""
Relationship, TimelineEvent, and Insight models.

Relationship: important people in the user's life (spouse, child, mentor, co-founder).
TimelineEvent: major past and anticipated life events (graduation, marriage, job change).
Insight: coaching reflections, lessons learned, and detected patterns (reflection memory).

See docs/DESIGN.md §5.1 (memory taxonomy).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Relationship(Base, TimestampMixin):
    __tablename__ = "relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    # spouse | child | parent | sibling | mentor | co-founder | friend | manager | …
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    # age, notes, emotional significance, etc.
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    # 1..5 subjective importance to the user's goals
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    __table_args__ = (Index("ix_relationships_user_id", "user_id"),)


class TimelineEvent(Base, TimestampMixin):
    __tablename__ = "timeline_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # graduation | marriage | job-change | birth | launch | …
    kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # True for planned future events ("expecting a baby", "target IPO date")
    is_anticipated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'")
    )

    __table_args__ = (
        Index("ix_timeline_events_user_id", "user_id"),
        Index("ix_timeline_events_date", "user_id", "event_date"),
    )


class Insight(Base, TimestampMixin):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coaching_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    # lesson | pattern | coaching-note | progress-reflection
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 1..5 importance rating
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    __table_args__ = (Index("ix_insights_user_id", "user_id"),)
