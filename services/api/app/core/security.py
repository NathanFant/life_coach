"""Auth boundary: verify Clerk-issued JWTs and resolve the current user.

This is the swap seam (docs/DESIGN.md §7.3): Clerk today, WorkOS/self-hosted
later — everything downstream depends only on `CurrentUser`, not on Clerk.
"""

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status


@dataclass(frozen=True)
class CurrentUser:
    id: str  # internal users.id (uuid)
    external_auth_id: str  # Clerk subject
    email: str


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> CurrentUser:
    """Validate `Authorization: Bearer <JWT>` and map to an app user.

    TODO (Phase 0): fetch JWKS, verify signature/issuer/exp, then upsert/lookup
    the local user row and set `app.user_id` for RLS.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "JWT verification not yet wired")


CurrentUserDep = Depends(get_current_user)
