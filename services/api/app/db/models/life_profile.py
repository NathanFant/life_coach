"""
LifeProfile and Domain models.

LifeProfile is 1:1 with User and holds the rolling structured summary of a user's life.
Domains represent individual life areas (career, family, finances…) with current and
desired states — these are the primary axes the coach works across.

See docs/DESIGN.md §2.2 and §4.3.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class LifeProfile(Base, TimestampMixin):
    __tablename__ = "life_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    life_stage: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Semi-structured attributes: age_range, marital_status, dependents, etc.
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    # Fraction 0..1 representing onboarding slot coverage
    completeness: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # ─── Relationships ───────────────────────────────────────────────────────
    user: Mapped[User] = relationship(back_populates="life_profile")  # type: ignore[name-defined]
    domains: Mapped[list[Domain]] = relationship(
        back_populates="life_profile", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_life_profiles_user_id", "user_id"),)


class Domain(Base, TimestampMixin):
    __tablename__ = "domains"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    life_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("life_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    # career | business | education | family | marriage | parenting |
    # finances | health | personal_growth | habits | productivity | side_project
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    current_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    desired_1y: Mapped[str | None] = mapped_column(Text, nullable=True)
    desired_5y: Mapped[str | None] = mapped_column(Text, nullable=True)
    obstacles: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    strengths: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    # Lower number = higher priority
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ─── Relationships ───────────────────────────────────────────────────────
    life_profile: Mapped[LifeProfile | None] = relationship(back_populates="domains")

    __table_args__ = (
        UniqueConstraint("user_id", "kind", name="uq_domains_user_kind"),
        Index("ix_domains_user_id", "user_id"),
        Index("ix_domains_user_kind", "user_id", "kind"),
    )


from app.db.models.user import User  # noqa: E402
