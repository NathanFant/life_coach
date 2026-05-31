"""Memory extraction (docs/DESIGN.md §5.2).

LLM proposes candidate facts/goals/projects/relationships/insights with a strict
JSON schema → dedupe via vector similarity → belief-revise contradictions → embed.
Idempotent on (session_id) so retries don't duplicate.
"""

# TODO (Phase 1): runs in a Celery worker, not the live request path.
