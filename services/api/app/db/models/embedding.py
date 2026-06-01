"""
Embedding model — the unified polymorphic vector index.

Points at any retrievable entity (episodic | semantic | insight | goal | project | message).
The HNSW index on the vector column provides approximate-nearest-neighbour search;
every query MUST filter by user_id first to preserve isolation and recall quality.

dim=1536 matches OpenAI text-embedding-3-small; update the migration and run the
embedding-backfill worker job when switching models (docs/DESIGN.md §5.6).

See docs/DESIGN.md §4.4 for the indexing strategy and §5.1 for the polymorphic design.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

EMBEDDING_DIM = 1536


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # episodic | semantic | insight | goal | project | message
    owner_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Which embedding model produced this vector — needed for migration/backfill
    model: Mapped[str] = mapped_column(Text, nullable=False)
    # The embedded text (used for re-ranking and debugging)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # The actual vector — HNSW index created in migration
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # Structured lookup by owner
        Index("ix_embeddings_user_owner", "user_id", "owner_type"),
        Index("ix_embeddings_owner", "owner_type", "owner_id"),
        # HNSW vector index is added in the Alembic migration (cannot be expressed
        # as a standard SA Index because of the vector operator class syntax)
    )
