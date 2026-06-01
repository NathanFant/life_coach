"""
Coaching orchestrator — the deterministic 6-step pipeline (docs/DESIGN.md §6.2).

    1. RETRIEVE   → memory pipeline assembles context (always-load + vector + structured)
    2. UNDERSTAND → intent + safety screen (before any LLM call)
    3. UPDATE     → tool calls mutate the life model (transactional, Phase 2)
    4. GUIDE      → stream coaching response (layered, cached prompt)
    5. ASK        → generate adaptive follow-up question(s)
    6. DETECT     → emit life-change / progress signals → feed memory + nudges

Not a free-roaming agent: a fixed pipeline with tool-calling, for reliability
and cost control.  Heavy memory work (extraction, consolidation) is deferred to
async Celery workers after the turn completes.

SSE event types (docs/DESIGN.md §9.3):
  token | tool_call | followups | change_detected | safety | done

Safety gate (step 2):
  CRISIS / INJECTION → immediate safety event, no LLM call, pipeline stops.
  MEDICAL / LEGAL / FINANCIAL → safety event (redirect), no coaching response.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from app.llm.coach_llm import CoachLLM, LLMMessage
from app.memory.service import ContextBundle, MemoryService
from app.safety.classifier import SafetyCategory, SafetyClassifier, is_blocking

logger = structlog.get_logger(__name__)

# Crisis resources returned with the safety event (localised in Phase 2)
_CRISIS_RESOURCES = [
    {"name": "988 Suicide & Crisis Lifeline (US)", "contact": "Call or text 988"},
    {"name": "Crisis Text Line (US)", "contact": "Text HOME to 741741"},
    {
        "name": "International Association for Suicide Prevention",
        "url": "https://www.iasp.info/resources/Crisis_Centres/",
    },
]

# Domain-boundary redirect messages
_REDIRECT_MESSAGES: dict[SafetyCategory, str] = {
    SafetyCategory.MEDICAL: (
        "I'm not able to give medical advice — that's best left to a licensed healthcare provider. "
        "I can help you plan how to find a doctor, prepare for an appointment, "
        "or make health-related goal decisions that are yours to make."
    ),
    SafetyCategory.LEGAL: (
        "Legal questions need a licensed attorney — I can't advise on specific legal situations. "
        "I can help you think through how to find the right lawyer, what questions to ask, "
        "or how to make decisions around the situation that are within your control."
    ),
    SafetyCategory.FINANCIAL: (
        "Specific investment or financial advice should come from a licensed financial advisor. "
        "I can help you clarify your financial goals, build a plan to engage a qualified advisor, "
        "or work through the decision-making process around your finances."
    ),
}

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


@dataclass
class OrchestratorConfig:
    coach_model: str
    extraction_model: str
    token_budget: int = 3000


class CoachingOrchestrator:
    """
    Provider-agnostic 6-step coaching pipeline.

    Inject a CoachLLM implementation (live or mocked) and a MemoryService.
    The orchestrator never imports LiteLLM or Postgres directly.
    """

    def __init__(
        self,
        llm: CoachLLM,
        memory: MemoryService,
        safety: SafetyClassifier,
        config: OrchestratorConfig,
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._safety = safety
        self._config = config
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        try:
            return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            return "You are a structured life coach. Help users make progress on their goals."

    async def run_turn(
        self,
        user_id: str,
        session_id: str,
        message: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Execute the 6-step pipeline and yield SSE event dicts.

        Callers: `async for event in orchestrator.run_turn(user_id, session_id, msg):`
        """
        async for event in self._pipeline(user_id, session_id, message):
            yield event

    async def _pipeline(
        self,
        user_id: str,
        session_id: str,
        message: str,
    ) -> AsyncIterator[dict[str, Any]]:
        # ── Step 2: UNDERSTAND — safety screen (before any LLM call) ──────────
        verdict = await self._safety.screen(message)
        if is_blocking(verdict):
            async for event in self._safety_response(verdict, session_id):
                yield event
            return

        # ── Step 1: RETRIEVE — assemble memory context ─────────────────────────
        context: ContextBundle = await self._memory.retrieve(
            user_id, message, token_budget=self._config.token_budget
        )

        # ── Step 4: GUIDE — stream coaching response ───────────────────────────
        messages = self._build_messages(context, message)
        async for token in self._llm.stream(messages, model=self._config.coach_model):
            yield {"event": "token", "data": token}

        # ── Step 5: ASK — follow-up questions (Phase 2: LLM-generated) ────────
        yield {
            "event": "followups",
            "questions": ["What feels most important to focus on first?"],
        }

        # ── Step 6: DETECT — life-change / progress signals ───────────────────
        # Phase 2: detect changes from the LLM response + tool calls
        # Phase 1: emit a placeholder
        yield {"event": "done", "session_id": session_id, "tokens_used": 0}

        # Note: memory extraction is enqueued by the caller (sessions endpoint),
        # not here — the orchestrator is agnostic to Celery/workers.

    def _build_messages(
        self,
        context: ContextBundle,
        user_message: str,
    ) -> list[LLMMessage]:
        """Assemble the layered prompt (docs/DESIGN.md §6.4)."""
        # System layer (cached)
        system = self._system_prompt

        # Profile + memory context layer
        memory_block = "\n\n".join(m.content for m in context.all_memories())
        if memory_block:
            system = f"{system}\n\n## What I know about you\n{memory_block}"

        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user_message),
        ]

    async def _safety_response(self, verdict, session_id: str) -> AsyncIterator[dict[str, Any]]:
        if verdict.category == SafetyCategory.CRISIS:
            yield {
                "event": "safety",
                "category": "crisis",
                "resources": _CRISIS_RESOURCES,
            }
        elif verdict.category == SafetyCategory.INJECTION:
            yield {
                "event": "safety",
                "category": "injection",
                "resources": [],
            }
        else:
            redirect_msg = _REDIRECT_MESSAGES.get(
                verdict.category,
                "I can't help with that specific request, but I can help you "
                "navigate it in a coaching capacity.",
            )
            yield {
                "event": "safety",
                "category": verdict.category.value,
                "redirect": redirect_msg,
                "resources": [],
            }
        yield {"event": "done", "session_id": session_id, "tokens_used": 0}
