"""SQLAlchemy declarative base + shared column mixins.

Concrete models (users, life_profiles, goals, ... see docs/DESIGN.md §4) live in
app/db/models/ and are added in Phase 0/1 alongside Alembic migrations.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
