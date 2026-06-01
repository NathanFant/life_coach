"""
Memory models: SemanticFact, EpisodicMemory, and Preference.

SemanticFact  — versioned, belief-revisable facts about the user.
EpisodicMemory — salient conversation summaries; the "what happened" layer.
Preference    — coaching and communication style; always loaded into context.

See docs/DESIGN.md §5.1 and §5.5 for the memory taxonomy and temporal model.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SemanticFact(Base, TimestampMixin):
    """
    A versioned belief about the user.

    When a fact changes (e.g. new job), the old row is closed (valid_to = now,
    superseded_by = new row id) and a new row is inserted.  This gives the coach
    a history ("you used to work at X; now you're founding a startup") and prevents
    stale beliefs from leaking into context (docs/DESIGN.md §5.5).
    """

    __tablename__ = "semantic_facts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # e.g. "occupation", "spouse_name", "age_range", "city", "annual_revenue"
    predicate: Mapped[str] = mapped_column(Text, nullable=False)
    # The believed value — flexible JSON to handle strings, numbers, lists
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # 0..1 — rises with repetition/confirmation, falls with contradiction/age
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    # onboarding | message | user-edit | inference | consolidation
    source: Mapped[str] = mapped_column(Text, nullable=False)
    # FK to the message or session that produced this fact
    source_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Temporal validity window (NULL valid_to = currently believed)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("semantic_facts.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        # Hot path: find all current facts for a user by predicate
        Index(
            "ix_semantic_facts_user_predicate_current",
            "user_id",
            "predicate",
            postgresql_where=text("valid_to IS NULL"),
        ),
        Index("ix_semantic_facts_user_id", "user_id"),
    )


class EpisodicMemory(Base, TimestampMixin):
    """
    A salient summary extracted from a coaching conversation.

    Salience, access count, and decay score drive the ranking formula
    (docs/DESIGN.md §5.3).  Consolidation jobs periodically distil clusters of
    episodes into semantic facts and lower their salience, then prune old ones.
    """

    __tablename__ = "episodic_memories"

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
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # 0..1 importance signal used by the ranking formula
    salience: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    # Coarse affect label: positive | negative | neutral | mixed
    emotion: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Computed by the consolidation job — lower = candidate for pruning
    decay_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (Index("ix_episodic_memories_user_salience", "user_id", "salience"),)


class Preference(Base):
    """
    User coaching and communication preferences.

    Always loaded into context (no vector retrieval needed) because they govern
    the tone and style of every coaching turn.  Evolves slowly via explicit user
    edits and inferred adjustments from the coach (docs/DESIGN.md §5.1).
    """

    __tablename__ = "preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # direct | warm | socratic | concise
    communication_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    # challenger | supporter | accountability | exploratory
    coaching_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    # intrinsic | achievement | fear-avoidant | social
    motivation_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Check-in frequency, notification preferences, etc.
    cadence: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_preferences_user_id", "user_id"),)
