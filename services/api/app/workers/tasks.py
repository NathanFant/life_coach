"""
Celery async task definitions (docs/DESIGN.md §5.2, §5.6).

Tasks are designed for:
  - Idempotency (safe to retry on failure)
  - Minimal data in the payload (IDs only, never large blobs)
  - Clear logging of start/complete/failure

Running workers:
  uv run celery -A app.workers.celery_app worker --loglevel=info
  uv run celery -A app.workers.celery_app beat --loglevel=info  (scheduled jobs)
"""

from __future__ import annotations

import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="memory.extract",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def extract_memory(self, user_id: str, session_id: str) -> None:
    """
    Extract structured memories from a completed coaching session.

    Idempotent on (user_id, session_id) — safe to retry.
    Uses a sync DB connection (Celery runs outside the async event loop).
    """
    logger.info("memory.extract.start", extra={"user_id": user_id, "session_id": session_id})
    try:
        _run_extraction(user_id, session_id)
        logger.info("memory.extract.done", extra={"user_id": user_id, "session_id": session_id})
    except Exception as exc:
        logger.warning(
            "memory.extract.failed",
            extra={"user_id": user_id, "session_id": session_id, "error": str(exc)},
        )
        self.retry(exc=exc)


def _run_extraction(user_id: str, session_id: str) -> None:
    """
    Sync entry point for extraction (runs in Celery worker process).

    TODO (Phase 1b): implement.
      1. Open a sync SQLAlchemy session.
      2. Load messages for the session.
      3. Call extract_from_session() with a LiteLLMCoachLLM instance.
      4. Persist extracted facts, insights, episodic memory.
      5. Generate and store embeddings for new entities.
    """
    pass  # Stubbed — Phase 1b


@celery_app.task(name="memory.consolidate")
def consolidate_memory(user_id: str) -> None:
    """
    Nightly: cluster episodic memories, distil into semantic facts, decay old ones.
    Scheduled via Celery Beat (Phase 2). TODO: implement.
    """
    pass


@celery_app.task(name="account.hard_delete")
def hard_delete_account(user_id: str) -> None:
    """
    GDPR hard-delete pipeline (docs/DESIGN.md §7.6):
      1. Soft-delete → status = 'deleting' (already set by the endpoint).
      2. Delete all user-owned rows (cascades via FK).
      3. Delete embeddings explicitly (large, separate table).
      4. Zero-retention: no action needed with zero-retention provider config.
      5. Write an immutable audit record.
    TODO (Phase 1): implement.
    """
    pass


@celery_app.task(name="account.export")
def export_account_data(user_id: str, export_id: str) -> None:
    """
    Assemble a full-data export (JSON + Markdown) and upload to S3 → signed URL.
    TODO (Phase 1): implement.
    """
    pass
