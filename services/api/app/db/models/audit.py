"""
AuditEvent model — append-only audit log.

No UPDATE or DELETE grants are given to the app role on this table.
Partitioned by month in Postgres to keep queries fast and enable cheap archival.

actor values: user id (UUID string), 'system', 'coach', 'worker'
action namespacing: domain.verb  e.g. auth.login, memory.write, data.export

See docs/DESIGN.md §4.6.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Text, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEvent(Base):
    """
    Immutable event record.  Explicitly no TimestampMixin — only created_at.
    No updated_at by design (append-only invariant).
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # NULL for system-initiated events with no authenticated user
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Who triggered the event
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    # auth.login | memory.write | data.export | account.delete | …
    action: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional resource type that was acted on
    resource: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    # Flexible metadata: resource id, old/new values, outcome, etc.
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_events_user_id", "user_id"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_created_at", "created_at"),
    )
