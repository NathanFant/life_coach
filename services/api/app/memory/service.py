"""
MemoryService — the interface the rest of the app depends on (docs/DESIGN.md §5).

The ONLY module that knows memory storage/retrieval internals.
Coaching depends on the MemoryService interface, so a pgvector → Qdrant swap stays local.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievedMemory:
    """A single memory unit returned by the retrieval pipeline."""

    owner_type: str  # episodic | semantic | insight | goal | project | message
    owner_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    # Optional embedding vector — used by MMR diversity selection (§5.3)
    embedding: list[float] = field(default_factory=list)


@dataclass
class ContextBundle:
    """
    The token-budgeted context block assembled for a coaching turn (docs/DESIGN.md §5.4).

    always_loaded: core identity facts, preferences, and active goals —
                   always included regardless of the query (anti-RAG-failure measure).
    recalled:      ranked, MMR-de-duplicated vector + structured recall.
    token_estimate: rough token count for the combined content.
    """

    always_loaded: list[RetrievedMemory]
    recalled: list[RetrievedMemory]
    token_estimate: int

    def all_memories(self) -> list[RetrievedMemory]:
        return self.always_loaded + self.recalled


class MemoryService:
    async def retrieve(
        self,
        user_id: str,
        query: str,
        *,
        token_budget: int = 3000,
    ) -> ContextBundle:
        """Hybrid retrieval: always-load + vector + structured, ranked + MMR (§5.3–5.4)."""
        raise NotImplementedError

    async def extract_and_store(self, user_id: str, session_id: str) -> None:
        """Async write path: extract → dedupe → belief-revise → embed (§5.2)."""
        raise NotImplementedError
