"""MemoryService — the interface the rest of the app depends on (docs/DESIGN.md §5)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievedMemory:
    owner_type: str  # episodic | semantic | insight | goal | project | message
    owner_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextBundle:
    """The token-budgeted context block assembled for a coaching turn (§5.4)."""

    always_loaded: list[RetrievedMemory]  # profile summary, prefs, active goals
    recalled: list[RetrievedMemory]  # ranked vector + structured recall
    token_estimate: int


class MemoryService:
    async def retrieve(self, user_id: str, query: str, *, token_budget: int = 3000) -> ContextBundle:
        """Hybrid retrieval: always-load + vector + structured, ranked + MMR (§5.3–5.4)."""
        raise NotImplementedError

    async def extract_and_store(self, user_id: str, session_id: str) -> None:
        """Async write path: extract → dedupe → belief-revise → embed (§5.2)."""
        raise NotImplementedError
