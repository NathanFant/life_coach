"""
Async SQLAlchemy engine, session factory, and FastAPI dependencies.

RLS (Row-Level Security) enforcement:
  Every session executes `SET LOCAL app.user_id = '<uuid>'` before any query
  so Postgres's RLS policies restrict visibility to the authenticated user's rows.
  The app role must NOT have BYPASSRLS privilege (docs/DESIGN.md §4.6).

Usage in endpoints:
    async def my_endpoint(db: AsyncSession = Depends(get_db_for_user)):
        ...
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import structlog
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import CurrentUser, CurrentUserDep
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def _raw_db() -> AsyncGenerator[AsyncSession, None]:
    """Raw session without RLS — for system-level operations (migrations, workers)."""
    async with SessionLocal() as session:
        yield session


async def get_db_for_user(
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = Depends(_raw_db),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Authenticated session with RLS applied.

    Sets `app.user_id` as a LOCAL Postgres setting for the duration of the
    transaction so all RLS policies activate transparently.  The `SET LOCAL`
    is scoped to the current transaction and is automatically reset on commit
    or rollback — no manual cleanup required.
    """
    # Look up the internal UUID for this Clerk subject.
    # This is cached in the future via Redis; for Phase 1 it's a direct query.
    row = await db.execute(
        text("SELECT id FROM users WHERE external_auth_id = :eid AND status = 'active'"),
        {"eid": current_user.external_auth_id},
    )
    user_row = row.first()
    if user_row is None:
        # First time we've seen this Clerk user — auto-provision
        user_id = await _provision_user(db, current_user)
    else:
        user_id = user_row[0]

    # Activate RLS for this session
    await db.execute(text(f"SET LOCAL app.user_id = '{user_id}'"))
    logger.debug("db.session.rls_set", user_id=str(user_id))

    yield db


async def _provision_user(db: AsyncSession, user: CurrentUser) -> uuid.UUID:
    """
    Create a new User row on first login.

    Called exactly once per Clerk user.  Idempotent on concurrent requests
    (ON CONFLICT DO NOTHING + retry).
    """
    new_id = uuid.uuid4()
    await db.execute(
        text("""
            INSERT INTO users
                (id, external_auth_id, email, email_verified, status, onboarding_state)
            VALUES (:id, :eid, :email, :ev, 'active', 'pending')
            ON CONFLICT (external_auth_id) DO NOTHING
        """),
        {
            "id": str(new_id),
            "eid": user.external_auth_id,
            "email": user.email,
            "ev": user.email_verified,
        },
    )
    await db.commit()
    # Re-fetch in case a concurrent request won the race
    row = await db.execute(
        text("SELECT id FROM users WHERE external_auth_id = :eid"),
        {"eid": user.external_auth_id},
    )
    user_row = row.first()
    assert user_row is not None
    logger.info("user.provisioned", external_auth_id=user.external_auth_id)
    return uuid.UUID(str(user_row[0]))


AuthedDB = Depends(get_db_for_user)
