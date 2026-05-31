"""Coaching tool surface (docs/DESIGN.md §6.3).

LLM-callable, server-side-validated (Pydantic), executed transactionally + audited.
"""

TOOL_NAMES = [
    "create_goal",
    "update_goal_progress",
    "create_project",
    "update_project_health",
    "create_milestone",
    "create_task",
    "complete_task",
    "upsert_relationship",
    "add_timeline_event",
    "record_insight",
    "flag_safety_concern",
    "request_user_confirmation",
]

# TODO (Phase 1): define JSON schemas + handlers per tool.
