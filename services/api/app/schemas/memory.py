"""Pydantic schemas for the memory browse/correct/forget endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import UUID4, BaseModel, Field


class MemoryItemOut(BaseModel):
    id: UUID4
    owner_type: str
    content: str
    score: float = Field(description="Relevance score from the retrieval pipeline")
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryPatchIn(BaseModel):
    content: str = Field(description="Corrected content — provenance is preserved")


class MemorySearchParams(BaseModel):
    query: str = ""
    owner_type: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
