"""
Coaching sessions — the streamed coaching loop (docs/DESIGN.md §3.4, §6.2).

POST /v1/sessions/{id}/messages runs the 6-step orchestrator pipeline and
streams the response via Server-Sent Events (SSE):
  token | tool_call | followups | change_detected | safety | done

The coaching session row is created lazily on first message.
After the turn completes, memory extraction is enqueued asynchronously.
"""

from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.coaching.orchestrator import CoachingOrchestrator, OrchestratorConfig
from app.core.auth import CurrentUser, CurrentUserDep
from app.core.config import get_settings
from app.db.session import AuthedDB
from app.llm.litellm_client import LiteLLMCoachLLM
from app.memory.retrieval import retrieve_context
from app.memory.service import MemoryService
from app.safety.classifier import SafetyClassifier
from app.schemas.coaching import MessageIn, SessionOut

router = APIRouter()
logger = structlog.get_logger(__name__)
_settings = get_settings()


def _build_orchestrator() -> CoachingOrchestrator:
    """Construct the orchestrator from application settings."""

    class _DBMemoryService(MemoryService):
        """Thin bridge connecting the orchestrator to the retrieval pipeline."""

        def __init__(self, db: AsyncSession, user_id: str) -> None:
            self._db = db
            self._user_id = user_id

        async def retrieve(self, user_id: str, query: str, *, token_budget: int = 3000):
            return await retrieve_context(self._db, user_id, query, token_budget=token_budget)

        async def extract_and_store(self, user_id: str, session_id: str) -> None:
            pass  # Handled by the endpoint after the turn

    # Return a factory that gets the orchestrator with a bound DB session
    # (built per-request in the endpoint)
    return None  # type: ignore[return-value]  — see _get_orchestrator below


async def _get_user_id(db: AsyncSession, eid: str) -> str:
    row = await db.execute(text("SELECT id FROM users WHERE external_auth_id = :eid"), {"eid": eid})
    r = row.first()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return str(r[0])


async def _ensure_session(db: AsyncSession, user_id: str, session_id: str) -> str:
    """Create the coaching_sessions row if it doesn't exist yet."""
    row = await db.execute(
        text("SELECT id FROM coaching_sessions WHERE id = :sid::uuid AND user_id = :uid::uuid"),
        {"sid": session_id, "uid": user_id},
    )
    if row.first() is None:
        await db.execute(
            text("""
                INSERT INTO coaching_sessions (id, user_id)
                VALUES (:sid::uuid, :uid::uuid)
                ON CONFLICT DO NOTHING
            """),
            {"sid": session_id, "uid": user_id},
        )
        await db.commit()
    return session_id


async def _sse_stream(
    user_id: str,
    session_id: str,
    message: str,
    db: AsyncSession,
):
    """Async generator that runs the orchestrator and formats SSE frames."""

    class _SessionMemory(MemoryService):
        async def retrieve(self, uid: str, query: str, *, token_budget: int = 3000):
            return await retrieve_context(db, uid, query, token_budget=token_budget)

        async def extract_and_store(self, uid: str, sid: str) -> None:
            pass

    llm = LiteLLMCoachLLM(model=_settings.coach_model)
    cfg = OrchestratorConfig(
        coach_model=_settings.coach_model,
        extraction_model=_settings.extraction_model,
    )
    orch = CoachingOrchestrator(
        llm=llm,
        memory=_SessionMemory(),
        safety=SafetyClassifier(llm=None),
        config=cfg,
    )

    async for event in orch.run_turn(user_id, session_id, message):
        yield f"data: {json.dumps(event)}\n\n"

    # Enqueue memory extraction after the turn
    try:
        from app.workers.tasks import extract_memory

        extract_memory.delay(user_id, session_id)
    except Exception:
        logger.warning("memory.extraction.enqueue_failed", user_id=user_id, session_id=session_id)


@router.post("/{session_id}/messages")
async def send_message(
    session_id: str,
    body: MessageIn,
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> StreamingResponse:
    """
    Send a message to the coaching session and stream the response via SSE.

    Creates the session row lazily if it doesn't exist.
    Streams event frames: `data: {"event": "...", ...}\n\n`
    """
    user_id = await _get_user_id(db, current_user.external_auth_id)
    await _ensure_session(db, user_id, session_id)

    logger.info("coaching.turn.start", user_id=user_id, session_id=session_id)

    return StreamingResponse(
        _sse_stream(user_id, session_id, body.content, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx: disable buffering for SSE
        },
    )


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: str,
    current_user: CurrentUser = CurrentUserDep,
    db: AsyncSession = AuthedDB,
) -> SessionOut:
    """Return session summary, detected life changes, and outcome actions."""
    user_id = await _get_user_id(db, current_user.external_auth_id)
    row = await db.execute(
        text("""
            SELECT id, focus_domain, summary, detected_changes, outcome_actions
            FROM coaching_sessions
            WHERE id = :sid::uuid AND user_id = :uid::uuid
        """),
        {"sid": session_id, "uid": user_id},
    )
    r = row.first()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return SessionOut(
        id=str(r[0]),
        focus_domain=r[1],
        summary=r[2],
        detected_changes=r[3] or [],
        outcome_actions=r[4] or [],
    )
