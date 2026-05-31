"""Coaching orchestrator — the deterministic 6-step pipeline (docs/DESIGN.md §6.2).

    RETRIEVE → UNDERSTAND → UPDATE → GUIDE → ASK → DETECT

Not a free-roaming agent: a fixed pipeline with tool-calling, for reliability and
cost control. Heavy memory work is deferred to async workers after the turn.
"""

from collections.abc import AsyncIterator

from app.llm.coach_llm import CoachLLM
from app.memory.service import MemoryService
from app.safety.classifier import SafetyClassifier


class CoachingOrchestrator:
    def __init__(
        self,
        llm: CoachLLM,
        memory: MemoryService,
        safety: SafetyClassifier,
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._safety = safety

    async def run_turn(
        self, user_id: str, session_id: str, message: str
    ) -> AsyncIterator[dict]:
        """Execute the pipeline and yield SSE events (token/tool_call/followups/...).

        TODO (Phase 1):
          1. RETRIEVE  → memory.retrieve(user_id, message)
          2. UNDERSTAND→ intent + sentiment + safety screen
          3. UPDATE    → tool calls mutate the life model (transactional)
          4. GUIDE     → stream coaching response (layered, cached prompt)
          5. ASK       → adaptive follow-up question(s)
          6. DETECT    → emit life-change / progress signals
          then enqueue memory.extract_and_store(user_id, session_id).
        """
        raise NotImplementedError
        yield  # pragma: no cover
