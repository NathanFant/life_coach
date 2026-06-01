"""
Safety classifier + escalation engine (docs/DESIGN.md §7.7, §10.3).

Design: two-stage screening
  Stage 1 (rule-based, synchronous) — pattern matching against known-bad signals.
            Fast, zero LLM cost, catches clear-cut cases.
  Stage 2 (LLM judge, async) — for genuinely ambiguous inputs, an LLM determines
            the category.  Only triggered when Stage 1 returns SAFE with low confidence.

Caller contract:
  verdict = await classifier.screen(text)
  if is_blocking(verdict):
      # do NOT proceed with coaching; return the escalation response

Crisis handling (docs/DESIGN.md §10.3):
  CRISIS verdicts must never be passed to the coaching pipeline.  The API layer
  must return a compassionate acknowledgement and localised crisis resources.

Thread safety:
  The classifier is stateless and safe to share across concurrent requests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.llm.coach_llm import CoachLLM


class SafetyCategory(StrEnum):
    SAFE = "safe"
    CRISIS = "crisis"  # self-harm / abuse / acute mental-health risk
    MEDICAL = "medical"  # medical diagnosis / prescription bait
    LEGAL = "legal"  # legal advice bait
    FINANCIAL = "financial"  # specific investment / financial advice bait
    INJECTION = "injection"  # prompt injection attempt


@dataclass
class SafetyVerdict:
    """The result of a safety screen."""

    category: SafetyCategory
    confidence: float  # 0..1
    rationale: str | None = field(default=None)


def is_blocking(verdict: SafetyVerdict) -> bool:
    """True for any category that must stop the coaching pipeline."""
    return verdict.category != SafetyCategory.SAFE


# ─── Rule-based signal patterns ───────────────────────────────────────────────────
# These are deliberately conservative — false negatives (missed threats) cost more
# than false positives (over-cautious redirections).

_CRISIS_PATTERNS = [
    r"\b(kill|end|take)\s+(my)?self\b",
    r"\b(suicide|suicidal)\b",
    r"\bdon't\s+want\s+to\s+(live|be\s+alive|exist)\b",
    r"\bendin[g]?\s+(it|it\s+all|my\s+life|everything)\b",
    r"\b(thoughts?\s+of|thinking\s+about)\s+(suicide|self.harm|hurting\s+myself)\b",
    r"\bself[\s\-]?harm(ing)?\b",
    r"\b(abuse|abusing)\s+me\b",
    # Indirect / euphemistic signals — captured from real-world patterns
    r"\b(no\s+point|no\s+reason)\s+(in|to)\s+(going|living|being\s+alive)\b",
    r"\b(won't|will\s+not|won.t)\s+be\s+around\s+(much\s+longer|anymore|for\s+long)\b",
    r"\bdon't\s+think\s+i('ll|.ll|\s+will)\s+be\s+around\b",
    r"\beveryone\s+(would\s+be|is)\s+better\s+off\s+without\s+me\b",
    r"\bno\s+point\s+in\s+going\s+on\b",
    r"\bfeel\s+like\s+there('s|\s+is)\s+no\s+point\b",
    # Direct crisis actions / plans
    r"\b(took|taken|taking)\s+(a\s+bunch\s+of|too\s+many|a\s+lot\s+of)\s+pills?\b",
    r"\bhave\s+a\s+plan\s+to\s+(end|kill|hurt)\b",
    r"\b(planning|plan\s+to)\s+(end\s+my\s+life|suicide|kill\s+myself)\b",
]

_MEDICAL_PATTERNS = [
    r"\b(diagnose|diagnosis|diagnoses)\b",
    r"\b(medication|prescribe|prescription|dosage|dose)\b",
    r"\bwhat\s+(medication|medicine|drug|pill)\b",
    r"\b(symptom|symptoms)\b.{0,50}\b(cause|meaning|treat|cure)\b",
    r"\bam\s+i\s+(sick|ill|depressed|anxious|bipolar|autistic)\b",
    # OTC drug / supplement queries  e.g. "Should I take ibuprofen for my headache?"
    r"\bshould\s+i\s+take\s+\w+\b.{0,30}\b(headache|pain|fever|cold|flu|symptom|anxiety|stress)\b",
    r"\b(ibuprofen|aspirin|tylenol|paracetamol|advil|benadryl|melatonin)\b",
]

_LEGAL_PATTERNS = [
    r"\b(lawsuit|sue|suing|litigate|litigation)\b",
    r"\b(legal\s+rights|my\s+rights\s+under)\b",
    r"\b(enforceable|breach\s+of\s+contract|wrongful\s+termination)\b",
    r"\b(non.compete|nda)\b.{0,50}\b(enforceable|valid|legal)\b",
    r"\bcan\s+i\s+(legally|sue|press\s+charges)\b",
]

_FINANCIAL_PATTERNS = [
    r"\bshould\s+i\s+(buy|sell|invest\s+in|buy\s+into)\b.{0,30}\b(stock|crypto|etf|fund|share)\b",
    r"\b(specific\s+investment|investment\s+advice)\b",
    r"\bwhich\s+(stock|crypto|coin|etf|fund)\s+should\s+i\b",
    r"\bwhat\s+(crypto|stock|coin)\s+should\s+i\s+(buy|invest)\b",
    r"\bgive\s+me\s+(investment|financial|portfolio)\s+advice\b",
]

_INJECTION_PATTERNS = [
    r"\bignore\s+(all\s+)?(previous|your|prior)\s+instructions?\b",
    r"\byou\s+(are\s+now|have\s+become|must\s+act\s+as)\s+(an\s+)?(unrestricted|unfiltered|jailbroken)\b",
    r"\bdisregard\s+(your\s+)?(safety|guidelines|rules|training|system\s+prompt)\b",
    r"\bforget\s+(your\s+)?(previous\s+)?(guidelines|instructions|system\s+prompt|training)\b",
    r"\bnew\s+system\s+prompt\b",
    r"\bsystem:\s*you\s+are\b",
    r"\b(reveal|expose|show\s+me)\s+(your\s+)?(system\s+prompt|instructions|rules)\b",
    # Jailbreak personas ("You are DAN", "act as an AI with no restrictions")
    r"\byou\s+are\s+(dan|jailbreak|an?\s+ai\s+with\s+no\s+(restrictions?|limits?|rules?))\b",
    r"\bact\s+as\s+(an?\s+)?(unrestricted|unfiltered|jailbroken|dan)\b",
    # Embedded injection in user-friendly framing
    r"\bplease\s+ignore\s+(safety|your|all)\s+(rules?|guidelines?|instructions?|restrictions?)\b",
]


def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE | re.DOTALL) for p in patterns]


_COMPILED: dict[SafetyCategory, list[re.Pattern[str]]] = {
    SafetyCategory.CRISIS: _compile(_CRISIS_PATTERNS),
    SafetyCategory.MEDICAL: _compile(_MEDICAL_PATTERNS),
    SafetyCategory.LEGAL: _compile(_LEGAL_PATTERNS),
    SafetyCategory.FINANCIAL: _compile(_FINANCIAL_PATTERNS),
    SafetyCategory.INJECTION: _compile(_INJECTION_PATTERNS),
}

# Priority order: CRISIS must always be checked first
_CATEGORY_PRIORITY = [
    SafetyCategory.CRISIS,
    SafetyCategory.INJECTION,
    SafetyCategory.MEDICAL,
    SafetyCategory.LEGAL,
    SafetyCategory.FINANCIAL,
]


class SafetyClassifier:
    """
    Two-stage safety classifier.

    Pass llm=None to disable Stage 2 (LLM judge) — only rule-based detection runs.
    In production, pass a CoachLLM instance so ambiguous cases are escalated.
    """

    def __init__(self, llm: CoachLLM | None = None) -> None:
        self._llm = llm

    async def screen(self, text: str) -> SafetyVerdict:
        """
        Screen text for safety violations.

        Returns immediately for clear-cut cases (rule-based Stage 1).
        Escalates to the LLM judge for ambiguous cases when an LLM is configured.
        """
        # Stage 1: rule-based
        verdict = _rule_based_screen(text)
        if verdict.category != SafetyCategory.SAFE:
            return verdict

        # Stage 2: LLM judge for low-confidence SAFE decisions
        # (Not yet implemented; returns SAFE for now — see Phase 1)
        return verdict


def _rule_based_screen(text: str) -> SafetyVerdict:
    """Return the first matching category in priority order, or SAFE."""
    for category in _CATEGORY_PRIORITY:
        patterns = _COMPILED[category]
        for pattern in patterns:
            if pattern.search(text):
                return SafetyVerdict(
                    category=category,
                    confidence=0.9,
                    rationale=f"Rule match: {pattern.pattern[:60]}",
                )
    return SafetyVerdict(category=SafetyCategory.SAFE, confidence=0.95)
