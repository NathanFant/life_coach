"""
LLMRouter — task-to-model mapping (docs/DESIGN.md §6.1).

Maps abstract task types to concrete model strings so callers never hardcode
provider/model strings.  Config values from Settings flow in at startup.

Adding a new task kind: extend TaskKind and add a case in model_for().
Changing a default model: update Settings and/or the router constructor.
"""

from __future__ import annotations

from enum import StrEnum


class TaskKind(StrEnum):
    COACHING = "coaching"  # live coaching turns — quality critical
    EXTRACTION = "extraction"  # memory fact extraction — volume, schema-bound
    ONBOARDING = "onboarding"  # adaptive interview — latency-sensitive
    EVALUATION = "evaluation"  # eval judge — should differ from generator
    EMBEDDING = "embedding"  # text → vector


class LLMRouter:
    """Maps TaskKind → model string.  Immutable after construction."""

    def __init__(
        self,
        *,
        coach_model: str,
        extraction_model: str,
        embedding_model: str,
        onboarding_model: str | None = None,
        eval_model: str | None = None,
    ) -> None:
        self._routes: dict[TaskKind, str] = {
            TaskKind.COACHING: coach_model,
            TaskKind.EXTRACTION: extraction_model,
            TaskKind.EMBEDDING: embedding_model,
            TaskKind.ONBOARDING: onboarding_model or coach_model,
            TaskKind.EVALUATION: eval_model or extraction_model,
        }

    def model_for(self, task: TaskKind) -> str:
        return self._routes[task]

    @classmethod
    def from_settings(cls) -> LLMRouter:
        """Construct from application settings (used in production)."""
        from app.core.config import get_settings

        s = get_settings()
        return cls(
            coach_model=s.coach_model,
            extraction_model=s.extraction_model,
            embedding_model=s.embedding_model,
        )
