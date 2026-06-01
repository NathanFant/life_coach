"""
Memory extraction pipeline (docs/DESIGN.md §5.2).

Runs asynchronously after each coaching turn in a Celery worker.
Does NOT block the live request path.

Steps:
  1. Load the coaching session's messages.
  2. Call the LLM with a structured extraction prompt to propose:
       - new/changed semantic facts
       - new goals, projects, tasks
       - relationship updates
       - timeline events
       - insights/reflections
  3. Deduplicate against existing facts via vector similarity.
  4. Perform belief revision for contradicting facts (close old, insert new).
  5. Generate embeddings for new/changed entities.
  6. Update the rolling life_profiles.summary.

Idempotent on (user_id, session_id): a unique constraint on
(user_id, session_id) in a future extraction_runs table prevents double-extraction.

This module runs inside Celery workers — it cannot use FastAPI request context.
It creates its own DB connection from DATABASE_URL_SYNC.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ─── Extraction prompt schema (passed as JSON schema to the LLM) ─────────────────
# The LLM must return a JSON object matching this structure.
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "semantic_facts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["predicate", "value", "confidence"],
                "properties": {
                    "predicate": {"type": "string"},
                    "value": {},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
        "goals": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "horizon"],
                "properties": {
                    "title": {"type": "string"},
                    "horizon": {"type": "string", "enum": ["short", "long"]},
                    "description": {"type": "string"},
                },
            },
        },
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["kind", "content"],
                "properties": {
                    "kind": {"type": "string"},
                    "content": {"type": "string"},
                    "importance": {"type": "integer", "minimum": 1, "maximum": 5},
                },
            },
        },
        "episodic_summary": {
            "type": "string",
            "description": "1-2 sentence summary of the most salient part of this session",
        },
        "life_changes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "confidence"],
                "properties": {
                    "type": {"type": "string"},
                    "confidence": {"type": "number"},
                },
            },
        },
    },
    "required": ["semantic_facts", "insights", "episodic_summary"],
    "additionalProperties": False,
}

EXTRACTION_PROMPT = """You are a structured memory extractor for an AI life coach.

Review the coaching conversation below and extract structured information about the user.
Be conservative — only extract facts that are clearly stated or strongly implied.
Do not invent or speculate.

Return a JSON object matching the provided schema exactly.

For semantic_facts: extract concrete facts (occupation, family situation, goals, challenges).
For insights: extract coaching observations, lessons learned, or patterns you noticed.
For episodic_summary: write 1-2 sentences capturing the most important thing that happened.
For life_changes: flag if the user mentioned a major life change
(new job, relationship change, etc.).

Conversation:
{conversation}
"""


async def extract_from_session(
    user_id: str,
    session_id: str,
    llm,  # CoachLLM
    db,  # AsyncSession
) -> dict:
    """
    Extract structured memories from a completed coaching session.

    Returns the extracted data dict for inspection/testing.
    TODO (Phase 1b): wire full extraction → dedupe → embed pipeline.
    """
    from sqlalchemy import text

    # Load recent messages for the session
    rows = await db.execute(
        text("""
            SELECT role, content FROM messages
            WHERE conversation_id IN (
                SELECT conversation_id FROM coaching_sessions
                WHERE id = :sid::uuid AND user_id = :uid::uuid
            )
            ORDER BY created_at
            LIMIT 50
        """),
        {"sid": session_id, "uid": user_id},
    )
    messages = rows.fetchall()
    if not messages:
        logger.info("extraction.no_messages", session_id=session_id)
        return {}

    conversation_text = "\n".join(f"{r[0].upper()}: {r[1]}" for r in messages)

    from app.llm.coach_llm import LLMMessage

    extraction_messages = [
        LLMMessage(role="user", content=EXTRACTION_PROMPT.format(conversation=conversation_text))
    ]

    response = await llm.generate(
        extraction_messages,
        response_format={"type": "json_object"},
    )

    try:
        import json

        extracted = json.loads(response.content)
    except (ValueError, KeyError):
        logger.warning("extraction.parse_failed", session_id=session_id)
        return {}

    logger.info(
        "extraction.complete",
        session_id=session_id,
        facts=len(extracted.get("semantic_facts", [])),
        insights=len(extracted.get("insights", [])),
    )

    # TODO (Phase 1b): persist extracted entities:
    #   - _store_semantic_facts(db, user_id, extracted["semantic_facts"])
    #   - _store_insights(db, user_id, session_id, extracted["insights"])
    #   - _store_episodic_memory(db, user_id, session_id, extracted["episodic_summary"])
    #   - _embed_new_entities(db, user_id, llm)
    #   - _update_profile_summary(db, user_id)

    return extracted
