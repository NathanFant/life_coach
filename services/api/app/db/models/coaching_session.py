"""
CoachingSession model — a single coaching interaction.

Tracks session-level metadata: which domain was focused on, what life changes were
detected, what outcome actions were proposed, and coarse sentiment.
Links back to the Conversation for the message transcript.

See docs/DESIGN.md §3.4 (request lifecycle) and §4.3.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CoachingSession(Base):
    __tablename__ = "coaching_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Which life domain was the primary focus of this session
    focus_domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # List of detected life-change signals: [{"type": "job_change", "confidence": 0.9}]
    detected_changes: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'")
    )
    # Proposed next actions from the session: [{"title": "...", "due": "..."}]
    outcome_actions: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'")
    )
    # Coarse sentiment: {"overall": "positive", "energy": "high"}
    sentiment: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_coaching_sessions_user_id", "user_id"),
        Index("ix_coaching_sessions_started_at", "user_id", "started_at"),
    )
