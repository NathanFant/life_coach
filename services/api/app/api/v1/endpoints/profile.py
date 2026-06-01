"""Life Profile read/edit. User edits are high-confidence memory signals."""

from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, CurrentUserDep
from app.db.session import AuthedDB
from app.schemas.profile import DomainOut, LifeProfileOut, ProfilePatchIn

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("", response_model=LifeProfileOut)
async def get_profile(
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> LifeProfileOut:
    """Return the user's life profile including all domains."""
    row = await db.execute(
        text("""
            SELECT lp.id, lp.life_stage, lp.summary, lp.completeness, lp.attributes
            FROM life_profiles lp
            JOIN users u ON lp.user_id = u.id
            WHERE u.external_auth_id = :eid
        """),
        {"eid": current_user.external_auth_id},
    )
    profile = row.first()
    if profile is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Life profile not found. Complete onboarding first.",
        )
    profile_id = str(profile[0])

    # Fetch domains
    domains_row = await db.execute(
        text("""
            SELECT id, kind, current_state, desired_1y, desired_5y,
                   obstacles, strengths, priority
            FROM domains WHERE user_id = (
                SELECT id FROM users WHERE external_auth_id = :eid
            )
            ORDER BY priority
        """),
        {"eid": current_user.external_auth_id},
    )

    domains = [
        DomainOut(
            id=str(r[0]),
            kind=r[1],
            current_state=r[2],
            desired_1y=r[3],
            desired_5y=r[4],
            obstacles=r[5] or [],
            strengths=r[6] or [],
            priority=r[7],
        )
        for r in domains_row.fetchall()
    ]

    return LifeProfileOut(
        id=profile_id,
        life_stage=profile[1],
        summary=profile[2],
        completeness=profile[3],
        attributes=profile[4] or {},
        domains=domains,
    )


@router.patch("", response_model=LifeProfileOut)
async def update_profile(
    body: ProfilePatchIn,
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> LifeProfileOut:
    """Apply user edits. Edits are recorded as high-confidence semantic facts."""
    updates: list[str] = []
    params: dict = {"eid": current_user.external_auth_id}

    if body.life_stage is not None:
        updates.append("life_stage = :life_stage")
        params["life_stage"] = body.life_stage
    if body.summary is not None:
        updates.append("summary = :summary")
        params["summary"] = body.summary
    if body.attributes is not None:
        updates.append("attributes = :attrs::jsonb")
        params["attrs"] = json.dumps(body.attributes)

    if updates:
        await db.execute(
            text(f"""
                UPDATE life_profiles
                SET {", ".join(updates)}, updated_at = now()
                WHERE user_id = (SELECT id FROM users WHERE external_auth_id = :eid)
            """),
            params,
        )
        await db.commit()

    return await get_profile(current_user=current_user, db=db)
