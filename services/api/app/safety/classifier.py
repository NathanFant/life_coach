"""Safety classifier + escalation (docs/DESIGN.md §7.7, §10.3).

Screens inputs and outputs for: crisis/self-harm, medical/legal/financial-advice
bait, and prompt injection. Routes to the escalation flow rather than coaching.
"""

from dataclasses import dataclass
from enum import Enum


class SafetyCategory(str, Enum):
    SAFE = "safe"
    CRISIS = "crisis"  # self-harm / abuse / acute risk → resources, stop coaching
    MEDICAL = "medical"
    LEGAL = "legal"
    FINANCIAL = "financial"
    INJECTION = "injection"


@dataclass
class SafetyVerdict:
    category: SafetyCategory
    confidence: float
    rationale: str | None = None


class SafetyClassifier:
    async def screen(self, text: str) -> SafetyVerdict:
        """TODO (Phase 1): classify; CRISIS → crisis-resource response + flag + audit."""
        raise NotImplementedError
