"""Onboarding: adaptive interview → structured Life Profile (docs/DESIGN.md §2.3)."""

from fastapi import APIRouter, status

router = APIRouter()


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_onboarding_state() -> dict:
    """Return current onboarding state + next adaptive question(s)."""
    return {"detail": "not_implemented"}


@router.post("/answer", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def submit_answer() -> dict:
    """Submit an answer; fill slot schema; return adaptive follow-up."""
    return {"detail": "not_implemented"}


@router.post("/complete", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def complete_onboarding() -> dict:
    """Finalize → seed Life Profile, goals, projects, semantic facts."""
    return {"detail": "not_implemented"}
