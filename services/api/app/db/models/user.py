"""
User model — the root entity.  Every user-owned table has a user_id FK here.

external_auth_id maps to the Clerk subject (docs/DESIGN.md §7.3).
Row-Level Security is enforced by setting `app.user_id` per transaction;
see app/db/session.py and docs/DESIGN.md §4.6.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, soft_delete


class User(Base, TimestampMixin, soft_delete):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    external_auth_id: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    # active | suspended | deleting
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    # pending | in_progress | complete
    onboarding_state: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # versioned GDPR consent record: {"tos": {"v": "1.0", "ts": "..."}, ...}
    consent: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))

    # ─── Relationships ───────────────────────────────────────────────────────
    life_profile: Mapped[LifeProfile | None] = relationship(back_populates="user", uselist=False)  # type: ignore[name-defined]

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_external_auth_id", "external_auth_id"),
        Index("ix_users_status", "status"),
    )


# Forward-reference resolved in life_profile.py
from app.db.models.life_profile import LifeProfile  # noqa: E402
