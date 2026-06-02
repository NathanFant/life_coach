"""
Onboarding answer parsing — converting free-text answers to structured values.

When a user submits a raw_answer to an onboarding question, the LLM parses it into
a structured representation that the Life Model can understand and reason about.

Examples:
  slot=EMPLOYMENT_STATUS, raw_answer="I'm building an AI startup with my co-founder"
  → {"status": "building_business", "type": "startup", "team": "co-founder"}

  slot=CAREER_GOAL_1Y, raw_answer="I want to get promoted to staff engineer"
  → {"goal": "staff_engineer_promotion", "role": "engineer", "level": "staff"}

If LLM keys are not configured, falls back to storing the raw answer as-is.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from app.llm.coach_llm import CoachLLM, LLMMessage
from app.onboarding.engine import DomainSlot

logger = structlog.get_logger(__name__)

# Slot-specific parsing schemas
_PARSING_SCHEMAS: dict[DomainSlot, dict[str, Any]] = {
    DomainSlot.EMPLOYMENT_STATUS: {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": [
                    "employed_fulltime",
                    "employed_parttime",
                    "freelance",
                    "building_business",
                    "self_employed",
                    "student",
                    "between_jobs",
                    "retired",
                ],
            },
            "role": {"type": "string"},
            "context": {"type": "string"},
        },
        "required": ["status"],
    },
    DomainSlot.RELATIONSHIP_STATUS: {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["single", "dating", "married", "partnership", "other"]},
            "context": {"type": "string"},
        },
        "required": ["status"],
    },
    DomainSlot.HAS_CHILDREN: {
        "type": "object",
        "properties": {
            "has_children": {"type": "boolean"},
            "count": {"type": "integer"},
            "ages": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["has_children"],
    },
    DomainSlot.EDUCATION_LEVEL: {
        "type": "object",
        "properties": {
            "level": {
                "type": "string",
                "enum": ["high_school", "some_college", "bachelor", "master", "phd", "self_taught"],
            },
            "field": {"type": "string"},
        },
        "required": ["level"],
    },
    DomainSlot.BUSINESS_STAGE: {
        "type": "object",
        "properties": {
            "stage": {
                "type": "string",
                "enum": ["idea", "pre_revenue", "early_traction", "growing", "scaling", "profitable"],
            },
            "detail": {"type": "string"},
        },
        "required": ["stage"],
    },
    DomainSlot.HAS_SIDE_PROJECT: {
        "type": "object",
        "properties": {
            "has_side_project": {"type": "boolean"},
            "type": {"type": "string"},
        },
        "required": ["has_side_project"],
    },
}


async def parse_answer(
    llm: CoachLLM | None,
    slot: DomainSlot,
    raw_answer: str,
) -> dict[str, Any]:
    """
    Parse a free-text answer into a structured value.

    If LLM is available and a schema exists for this slot, uses the LLM to extract
    structured data. Otherwise, stores the raw answer as-is.

    Args:
        llm: CoachLLM instance (None if keys not configured)
        slot: The onboarding slot being answered
        raw_answer: The user's free-text response

    Returns:
        A structured value to store in the Life Profile
    """
    # If no LLM is available, store the raw answer
    if llm is None:
        return {"value": raw_answer, "parsed": False}

    # If no schema exists for this slot, store the raw answer
    schema = _PARSING_SCHEMAS.get(slot)
    if schema is None:
        return {"value": raw_answer, "parsed": False}

    try:
        # Use the LLM to parse the answer into structured format
        prompt = f"""
You are parsing a user's answer to a life coaching question.

Slot: {slot.value}
User's answer: {raw_answer}

Extract the relevant information into the specified JSON structure. Be generous
with interpretation — if the user's answer implies something, infer it.
If a field is not mentioned, omit it (don't use null).

Expected schema:
{json.dumps(schema, indent=2)}

Respond ONLY with valid JSON matching the schema. No other text.
""".strip()

        resp = await llm.generate(
            [LLMMessage(role="user", content=prompt)],
            model=None,  # Use default model
            response_format={"type": "json_object"},
        )

        parsed = json.loads(resp.content)
        return {**parsed, "parsed": True}

    except Exception as e:
        logger.warning("parse_answer_failed", slot=slot.value, error=str(e))
        # Fall back to storing the raw answer
        return {"value": raw_answer, "parsed": False}
