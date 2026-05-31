"""Aggregates all v1 routers. Endpoints map to docs/DESIGN.md §9.2."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    account,
    goals,
    memory,
    onboarding,
    profile,
    sessions,
)

api_router = APIRouter()
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(goals.router, prefix="/goals", tags=["goals"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["coaching"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(account.router, prefix="/account", tags=["privacy"])
