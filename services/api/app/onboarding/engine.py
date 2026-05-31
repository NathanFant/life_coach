"""Adaptive onboarding engine (docs/DESIGN.md §2.3).

Hybrid: a deterministic question graph (domains → slot schema) governs coverage and
branching; an LLM phrases questions, asks follow-ups, and decides slot satisfaction.
Output: a populated Life Profile + seeded goals/projects/relationships/semantic facts.
"""

# Domain coverage targets for the slot schema (see DomainKind in @repo/types).
ONBOARDING_DOMAINS = [
    "education",
    "career",
    "business",
    "side_project",
    "family",
    "marriage",
    "parenting",
    "finances",
    "personal_growth",
    "habits",
]

# TODO (Phase 1): question graph, branching rules, slot-satisfaction, resumability.
