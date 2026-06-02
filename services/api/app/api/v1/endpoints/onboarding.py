"""
Onboarding: adaptive interview → structured Life Profile (docs/DESIGN.md §2.3).

Flow:
  GET  /onboarding          → current state + next question
  POST /onboarding/answer   → submit answer, get updated state + next question
  POST /onboarding/complete → finalise → seed Life Profile, goals, projects

Onboarding state is stored in users.onboarding_state as a JSON blob (Phase 1).
Phase 2 will migrate to a dedicated onboarding_sessions table.
"""

from __future__ import annotations

import json
import uuid

import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, CurrentUserDep
from app.core.config import get_settings
from app.db.session import AuthedDB
from app.llm.litellm_client import LiteLLMCoachLLM
from app.onboarding.engine import (
    DomainSlot,
    OnboardingState,
    QuestionGraph,
    build_initial_state,
)
from app.onboarding.parsing import parse_answer
from app.schemas.onboarding import (
    AnswerIn,
    OnboardingCompleteResponse,
    OnboardingStateResponse,
    QuestionOut,
)

router = APIRouter()
logger = structlog.get_logger(__name__)
_graph = QuestionGraph()


# ─── State persistence helpers ───────────────────────────────────────────────────


async def _get_user_id(db: AsyncSession, external_auth_id: str) -> str:
    row = await db.execute(
        text("SELECT id FROM users WHERE external_auth_id = :eid"),
        {"eid": external_auth_id},
    )
    r = row.first()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return str(r[0])


async def _load_state(db: AsyncSession, user_id: str) -> OnboardingState:
    row = await db.execute(
        text("SELECT onboarding_state FROM users WHERE id = :uid::uuid"),
        {"uid": user_id},
    )
    result = row.first()
    if result is None:
        return build_initial_state()
    raw = result[0]
    if not raw or raw in ("pending", "complete"):
        return build_initial_state()
    try:
        return OnboardingState.from_dict(json.loads(raw))
    except (ValueError, KeyError):
        return build_initial_state()


async def _save_state(db: AsyncSession, user_id: str, state: OnboardingState) -> None:
    serialised = json.dumps(state.to_dict())
    await db.execute(
        text("UPDATE users SET onboarding_state = :s WHERE id = :uid::uuid"),
        {"s": serialised, "uid": user_id},
    )
    await db.commit()


def _state_to_response(state: OnboardingState) -> OnboardingStateResponse:
    q = _graph.next_question(state)
    return OnboardingStateResponse(
        is_complete=state.is_complete(),
        completeness=state.schema.completeness(),
        next_question=QuestionOut(slot=q.slot, text=q.text, hint=q.hint) if q else None,
        filled_slots={k: v for k, v in state.schema.to_dict().items()},
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────────


@router.get("", response_model=OnboardingStateResponse)
async def get_onboarding_state(
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> OnboardingStateResponse:
    """Return current onboarding state and the next adaptive question."""
    user_id = await _get_user_id(db, current_user.external_auth_id)
    state = await _load_state(db, user_id)
    return _state_to_response(state)


@router.post("/answer", response_model=OnboardingStateResponse)
async def submit_answer(
    body: AnswerIn,
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> OnboardingStateResponse:
    """
    Submit an answer to the current onboarding question.

    If a raw_answer is provided, it's parsed via LLM into structured format.
    If structured_value is provided, it's used as-is (for testing).
    """
    user_id = await _get_user_id(db, current_user.external_auth_id)
    state = await _load_state(db, user_id)

    try:
        slot = DomainSlot(body.slot)
    except ValueError:
        raise HTTPException(  # noqa: B904
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown slot: {body.slot!r}",
        )

    # If structured_value is provided, use it directly (for testing)
    if body.structured_value is not None:
        value = body.structured_value
    else:
        # Parse the raw answer using the LLM
        llm = LiteLLMCoachLLM(model=get_settings().extraction_model)
        value = await parse_answer(llm, slot, body.raw_answer)

    state.schema.mark_filled(slot, value)

    await _save_state(db, user_id, state)
    logger.info("onboarding.answer", user_id=user_id, slot=body.slot)

    return _state_to_response(state)


@router.post("/complete", response_model=OnboardingCompleteResponse)
async def complete_onboarding(
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> OnboardingCompleteResponse:
    """
    Finalise onboarding → create Life Profile and seed semantic facts.

    Can be called before 100% coverage; coaching fills remaining gaps.
    """
    user_id = await _get_user_id(db, current_user.external_auth_id)
    state = await _load_state(db, user_id)

    profile_id = await _upsert_life_profile(db, user_id, state)

    await db.execute(
        text("UPDATE users SET onboarding_state = 'complete' WHERE id = :uid::uuid"),
        {"uid": user_id},
    )
    await db.commit()
    logger.info("onboarding.complete", user_id=user_id, profile_id=profile_id)

    return OnboardingCompleteResponse(
        life_profile_id=profile_id,
        completeness=state.schema.completeness(),
    )


async def _upsert_life_profile(db: AsyncSession, user_id: str, state: OnboardingState) -> str:
    attrs = json.dumps({k: v for k, v in state.schema.to_dict().items()})
    row = await db.execute(
        text("SELECT id FROM life_profiles WHERE user_id = :uid::uuid"),
        {"uid": user_id},
    )
    existing = row.first()
    if existing:
        profile_id = str(existing[0])
        await db.execute(
            text("""
                UPDATE life_profiles
                SET attributes = :attrs::jsonb, completeness = :c, updated_at = now()
                WHERE id = :pid::uuid
            """),
            {"attrs": attrs, "c": state.schema.completeness(), "pid": profile_id},
        )
    else:
        profile_id = str(uuid.uuid4())
        await db.execute(
            text("""
                INSERT INTO life_profiles (id, user_id, attributes, completeness)
                VALUES (:pid::uuid, :uid::uuid, :attrs::jsonb, :c)
            """),
            {"pid": profile_id, "uid": user_id, "attrs": attrs, "c": state.schema.completeness()},
        )
    await db.commit()
    return profile_id
