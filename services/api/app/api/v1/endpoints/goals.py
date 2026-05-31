"""Goals CRUD (and, by extension, projects/milestones/tasks — see docs/DESIGN.md §4)."""

from fastapi import APIRouter, status

router = APIRouter()


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def list_goals() -> dict:
    return {"detail": "not_implemented"}


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_goal() -> dict:
    return {"detail": "not_implemented"}


@router.patch("/{goal_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def update_goal(goal_id: str) -> dict:
    return {"detail": "not_implemented", "goal_id": goal_id}
