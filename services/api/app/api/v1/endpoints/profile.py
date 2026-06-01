"""Life Profile read/edit. User edits are high-confidence memory signals."""

from fastapi import APIRouter, status

from app.core.auth import CurrentUser, CurrentUserDep

router = APIRouter()


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_profile(current_user: CurrentUser = CurrentUserDep) -> dict:
    """Return life profile + domains + rolling summary."""
    return {"detail": "not_implemented"}


@router.patch("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def update_profile(current_user: CurrentUser = CurrentUserDep) -> dict:
    """Apply user edits (recorded as high-confidence semantic facts)."""
    return {"detail": "not_implemented"}
