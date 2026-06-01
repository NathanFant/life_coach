"""
Adaptive onboarding engine (docs/DESIGN.md §2.3).

Architecture: deterministic question graph + slot schema.
  - QuestionGraph drives coverage and branching (which slot to ask next).
  - SlotSchema tracks which facts are known and computes completeness.
  - OnboardingState holds the current SlotSchema and is serialisable so sessions
    can be paused and resumed (stored in the coaching_sessions row).
  - The LLM is used to phrase questions naturally and to evaluate free-text
    answers into structured slot values (wired in Phase 1 endpoints).

Branching rules:
  has_children == False  → skip PARENTING_STYLE, PARENTING_CHALLENGES
  employment_status == "building_business" → add BUSINESS_STAGE, BUSINESS_REVENUE
  relationship_status == "single"          → skip MARRIAGE_* slots

COMPLETION_THRESHOLD: fraction of mandatory slots that must be filled.
Coaching can start before 100% coverage; the coach fills gaps opportunistically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# ─── Slot identifiers ────────────────────────────────────────────────────────────


class DomainSlot(StrEnum):
    # Core identity
    AGE_RANGE = "age_range"
    RELATIONSHIP_STATUS = "relationship_status"
    HAS_CHILDREN = "has_children"
    PARENTING_STYLE = "parenting_style"
    PARENTING_CHALLENGES = "parenting_challenges"
    # Career / employment
    EMPLOYMENT_STATUS = "employment_status"
    JOB_TITLE = "job_title"
    INDUSTRY = "industry"
    YEARS_EXPERIENCE = "years_experience"
    CAREER_GOAL_1Y = "career_goal_1y"
    CAREER_GOAL_5Y = "career_goal_5y"
    # Business / entrepreneurship
    BUSINESS_STAGE = "business_stage"
    BUSINESS_REVENUE = "business_revenue"
    BUSINESS_COFOUNDER = "business_cofounder"
    # Education
    EDUCATION_LEVEL = "education_level"
    # Current focus
    PRIMARY_STRESS = "primary_stress"
    BIGGEST_OPPORTUNITY = "biggest_opportunity"
    # Side projects
    HAS_SIDE_PROJECT = "has_side_project"
    SIDE_PROJECT_DESCRIPTION = "side_project_description"
    # Finances
    FINANCIAL_SITUATION = "financial_situation"
    FINANCIAL_GOAL = "financial_goal"
    # Personal growth
    PERSONAL_GROWTH_FOCUS = "personal_growth_focus"


# ─── Question node ────────────────────────────────────────────────────────────────


@dataclass
class Question:
    """A single onboarding question ready to send to the user."""

    slot: DomainSlot
    text: str
    hint: str = ""  # optional placeholder / example answer


# ─── Slot schema ──────────────────────────────────────────────────────────────────

# Slots that must be filled (or explicitly skipped) for onboarding to be "done"
_MANDATORY_SLOTS: list[DomainSlot] = [
    DomainSlot.EMPLOYMENT_STATUS,
    DomainSlot.RELATIONSHIP_STATUS,
    DomainSlot.HAS_CHILDREN,
    DomainSlot.EDUCATION_LEVEL,
    DomainSlot.PRIMARY_STRESS,
    DomainSlot.BIGGEST_OPPORTUNITY,
    DomainSlot.CAREER_GOAL_1Y,
    DomainSlot.CAREER_GOAL_5Y,
    DomainSlot.FINANCIAL_SITUATION,
    DomainSlot.FINANCIAL_GOAL,
    DomainSlot.PERSONAL_GROWTH_FOCUS,
    DomainSlot.HAS_SIDE_PROJECT,
]

COMPLETION_THRESHOLD = 0.8  # 80% of mandatory slots → onboarding "complete"


class SlotSchema:
    """Tracks which facts are known about the user."""

    def __init__(self) -> None:
        self._filled: dict[str, Any] = {}

    def mandatory_slots(self) -> list[DomainSlot]:
        return list(_MANDATORY_SLOTS)

    def mark_filled(self, slot: DomainSlot, value: Any) -> None:
        self._filled[slot.value] = value

    def mark_skipped(self, slot: DomainSlot) -> None:
        """Explicitly skip a slot (e.g. parenting for childless users)."""
        self._filled[slot.value] = {"_skipped": True}

    def is_filled(self, slot: DomainSlot) -> bool:
        return slot.value in self._filled

    def get_value(self, slot: DomainSlot) -> Any | None:
        v = self._filled.get(slot.value)
        if isinstance(v, dict) and v.get("_skipped"):
            return None
        return v

    def completeness(self) -> float:
        if not _MANDATORY_SLOTS:
            return 1.0
        filled = sum(1 for s in _MANDATORY_SLOTS if s.value in self._filled)
        return min(1.0, filled / len(_MANDATORY_SLOTS))

    def to_dict(self) -> dict[str, Any]:
        return dict(self._filled)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlotSchema:
        schema = cls()
        schema._filled = dict(data)
        return schema


# ─── Question graph ───────────────────────────────────────────────────────────────

# Default question text for each slot (the LLM will rephrase these naturally)
_DEFAULT_QUESTIONS: dict[DomainSlot, Question] = {
    DomainSlot.EMPLOYMENT_STATUS: Question(
        DomainSlot.EMPLOYMENT_STATUS,
        "Are you currently employed, self-employed, building a business, or something else?",
        "e.g. employed full-time, freelancer, founder, student, between jobs",
    ),
    DomainSlot.JOB_TITLE: Question(
        DomainSlot.JOB_TITLE,
        "What do you do for work?",
        "e.g. Software engineer, Marketing manager, Product lead",
    ),
    DomainSlot.INDUSTRY: Question(
        DomainSlot.INDUSTRY,
        "What industry or sector are you in?",
        "e.g. Tech, Healthcare, Finance, Education",
    ),
    DomainSlot.CAREER_GOAL_1Y: Question(
        DomainSlot.CAREER_GOAL_1Y,
        "Where do you want to be in your career in 1 year?",
    ),
    DomainSlot.CAREER_GOAL_5Y: Question(
        DomainSlot.CAREER_GOAL_5Y,
        "Where do you want to be professionally in 5 years?",
    ),
    DomainSlot.BUSINESS_STAGE: Question(
        DomainSlot.BUSINESS_STAGE,
        "What stage is your business at?",
        "e.g. idea, pre-revenue, early traction, scaling",
    ),
    DomainSlot.BUSINESS_REVENUE: Question(
        DomainSlot.BUSINESS_REVENUE,
        "Is the business generating revenue yet? If so, roughly what stage?",
    ),
    DomainSlot.BUSINESS_COFOUNDER: Question(
        DomainSlot.BUSINESS_COFOUNDER,
        "Are you building this solo or with co-founders?",
    ),
    DomainSlot.RELATIONSHIP_STATUS: Question(
        DomainSlot.RELATIONSHIP_STATUS,
        "Are you single, in a relationship, married, or something else?",
    ),
    DomainSlot.HAS_CHILDREN: Question(
        DomainSlot.HAS_CHILDREN,
        "Do you have children or dependents?",
    ),
    DomainSlot.PARENTING_STYLE: Question(
        DomainSlot.PARENTING_STYLE,
        "How old are your children, and what parenting challenges are top of mind?",
    ),
    DomainSlot.PARENTING_CHALLENGES: Question(
        DomainSlot.PARENTING_CHALLENGES,
        "What's the biggest challenge you're navigating as a parent right now?",
    ),
    DomainSlot.EDUCATION_LEVEL: Question(
        DomainSlot.EDUCATION_LEVEL,
        "What's your highest level of education completed?",
        "e.g. high school, bachelor's, master's, PhD, self-taught",
    ),
    DomainSlot.PRIMARY_STRESS: Question(
        DomainSlot.PRIMARY_STRESS,
        "What's causing you the most stress or friction right now?",
    ),
    DomainSlot.BIGGEST_OPPORTUNITY: Question(
        DomainSlot.BIGGEST_OPPORTUNITY,
        "What do you see as your biggest opportunity right now?",
    ),
    DomainSlot.HAS_SIDE_PROJECT: Question(
        DomainSlot.HAS_SIDE_PROJECT,
        "Are you working on anything outside of your main job or business?",
    ),
    DomainSlot.SIDE_PROJECT_DESCRIPTION: Question(
        DomainSlot.SIDE_PROJECT_DESCRIPTION,
        "Tell me about your side project — what is it and where are you with it?",
    ),
    DomainSlot.FINANCIAL_SITUATION: Question(
        DomainSlot.FINANCIAL_SITUATION,
        "How would you describe your financial situation right now?",
        "e.g. building savings, paying off debt, investing, financially stable",
    ),
    DomainSlot.FINANCIAL_GOAL: Question(
        DomainSlot.FINANCIAL_GOAL,
        "What's your most important financial goal right now?",
    ),
    DomainSlot.PERSONAL_GROWTH_FOCUS: Question(
        DomainSlot.PERSONAL_GROWTH_FOCUS,
        "What area of personal growth or self-improvement matters most to you right now?",
        "e.g. habits, mindset, health, communication, creativity",
    ),
    DomainSlot.AGE_RANGE: Question(
        DomainSlot.AGE_RANGE,
        "What's your approximate age range?",
        "e.g. early 20s, late 30s, mid-50s",
    ),
    DomainSlot.YEARS_EXPERIENCE: Question(
        DomainSlot.YEARS_EXPERIENCE,
        "How many years of professional experience do you have?",
    ),
}


class QuestionGraph:
    """
    Determines which slot to ask next given the current onboarding state.

    Ordering and branching are deterministic — the LLM is only used to
    phrase the question naturally (wired in the endpoint layer).
    """

    # Ordered list of slots; branching is applied before selecting the next
    _DEFAULT_ORDER: list[DomainSlot] = [
        DomainSlot.EMPLOYMENT_STATUS,
        DomainSlot.CAREER_GOAL_1Y,
        DomainSlot.CAREER_GOAL_5Y,
        DomainSlot.RELATIONSHIP_STATUS,
        DomainSlot.HAS_CHILDREN,
        DomainSlot.EDUCATION_LEVEL,
        DomainSlot.PRIMARY_STRESS,
        DomainSlot.BIGGEST_OPPORTUNITY,
        DomainSlot.HAS_SIDE_PROJECT,
        DomainSlot.FINANCIAL_SITUATION,
        DomainSlot.FINANCIAL_GOAL,
        DomainSlot.PERSONAL_GROWTH_FOCUS,
        # Conditional slots (inserted by branching)
        DomainSlot.PARENTING_STYLE,
        DomainSlot.PARENTING_CHALLENGES,
        DomainSlot.BUSINESS_STAGE,
        DomainSlot.BUSINESS_REVENUE,
        DomainSlot.BUSINESS_COFOUNDER,
        DomainSlot.SIDE_PROJECT_DESCRIPTION,
    ]

    def next_question(self, state: OnboardingState) -> Question | None:
        """
        Return the next Question to ask, or None if coverage is complete.

        Applies branching rules before selecting: if a branching condition
        precludes a slot, that slot is auto-skipped.  Conditional slots are
        moved immediately after the trigger slot so the conversation flows
        naturally (e.g. business questions follow employment, not come last).
        """
        self._apply_branching(state)
        for slot in self._dynamic_order(state):
            if not state.schema.is_filled(slot):
                return _DEFAULT_QUESTIONS.get(slot)
        return None

    def _dynamic_order(self, state: OnboardingState) -> list[DomainSlot]:
        """Build a context-aware slot ordering based on what's already known."""
        # Base order (mandatory + conditional)
        order = [
            DomainSlot.EMPLOYMENT_STATUS,
        ]
        # Insert business slots immediately if building a business
        emp = state.schema.get_value(DomainSlot.EMPLOYMENT_STATUS)
        if emp is not None and _str_value(emp) in (
            "building_business",
            "self-employed",
            "founder",
            "entrepreneur",
        ):
            order += [
                DomainSlot.BUSINESS_STAGE,
                DomainSlot.BUSINESS_REVENUE,
                DomainSlot.BUSINESS_COFOUNDER,
            ]
        order += [
            DomainSlot.CAREER_GOAL_1Y,
            DomainSlot.CAREER_GOAL_5Y,
            DomainSlot.RELATIONSHIP_STATUS,
            DomainSlot.HAS_CHILDREN,
            DomainSlot.PARENTING_STYLE,
            DomainSlot.PARENTING_CHALLENGES,
            DomainSlot.EDUCATION_LEVEL,
            DomainSlot.PRIMARY_STRESS,
            DomainSlot.BIGGEST_OPPORTUNITY,
            DomainSlot.HAS_SIDE_PROJECT,
            DomainSlot.SIDE_PROJECT_DESCRIPTION,
            DomainSlot.FINANCIAL_SITUATION,
            DomainSlot.FINANCIAL_GOAL,
            DomainSlot.PERSONAL_GROWTH_FOCUS,
        ]
        return order

    def _apply_branching(self, state: OnboardingState) -> None:
        """Auto-skip slots that are not applicable given what we already know."""
        schema = state.schema

        # No children → skip parenting slots
        has_children = schema.get_value(DomainSlot.HAS_CHILDREN)
        if has_children is not None and not _truthy(has_children):
            schema.mark_skipped(DomainSlot.PARENTING_STYLE)
            schema.mark_skipped(DomainSlot.PARENTING_CHALLENGES)

        # Not building a business → skip entrepreneurship slots
        employment = schema.get_value(DomainSlot.EMPLOYMENT_STATUS)
        if employment is not None:
            emp_val = _str_value(employment)
            if emp_val not in ("building_business", "self-employed", "founder", "entrepreneur"):
                schema.mark_skipped(DomainSlot.BUSINESS_STAGE)
                schema.mark_skipped(DomainSlot.BUSINESS_REVENUE)
                schema.mark_skipped(DomainSlot.BUSINESS_COFOUNDER)

        # No side project → skip side project description
        has_side = schema.get_value(DomainSlot.HAS_SIDE_PROJECT)
        if has_side is not None and not _truthy(has_side):
            schema.mark_skipped(DomainSlot.SIDE_PROJECT_DESCRIPTION)


def _truthy(value: Any) -> bool:
    """Evaluate a slot value as a boolean."""
    if isinstance(value, dict):
        v = value.get("value", value)
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() not in ("false", "no", "n", "0", "none", "null")
        return bool(v)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in ("false", "no", "n", "0", "none", "null")
    return bool(value)


def _str_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value", "")).lower()
    return str(value).lower()


# ─── Onboarding state ─────────────────────────────────────────────────────────────


@dataclass
class OnboardingState:
    """The full mutable state of an onboarding session. Serialisable."""

    schema: SlotSchema = field(default_factory=SlotSchema)

    def is_complete(self) -> bool:
        return self.schema.completeness() >= COMPLETION_THRESHOLD

    def to_dict(self) -> dict[str, Any]:
        return {"slots": self.schema.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OnboardingState:
        schema = SlotSchema.from_dict(data.get("slots", {}))
        return cls(schema=schema)


def build_initial_state() -> OnboardingState:
    return OnboardingState(schema=SlotSchema())
