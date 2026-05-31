"""Coaching sessions — the streamed coaching loop (docs/DESIGN.md §3.4, §6.2).

POST /sessions/{id}/messages runs the 6-step pipeline and streams the response
back over SSE: token / tool_call / followups / change_detected / safety / done.
"""

from fastapi import APIRouter, status

router = APIRouter()


@router.post("/{session_id}/messages", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def send_message(session_id: str) -> dict:
    """Run the coaching orchestrator and stream the response (SSE).

    TODO (Phase 1): retrieve → understand → update → guide → ask → detect,
    then enqueue async memory extraction.
    """
    return {"detail": "not_implemented", "session_id": session_id}


@router.get("/{session_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_session(session_id: str) -> dict:
    """Session summary, detected life changes, and outcome actions."""
    return {"detail": "not_implemented", "session_id": session_id}
