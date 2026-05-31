"""Async task definitions (docs/DESIGN.md §5.2, §5.6)."""

from app.workers.celery_app import celery_app


@celery_app.task(name="memory.extract", bind=True, max_retries=3)
def extract_memory(self, user_id: str, session_id: str) -> None:  # noqa: ANN001, ARG001
    """Post-turn memory extraction (idempotent on session_id). TODO: implement."""
    raise NotImplementedError


@celery_app.task(name="memory.consolidate")
def consolidate_memory(user_id: str) -> None:
    """Nightly consolidation/decay/reflection. TODO: implement."""
    raise NotImplementedError


@celery_app.task(name="account.hard_delete")
def hard_delete_account(user_id: str) -> None:
    """GDPR hard-delete pipeline (rows + embeddings + audit). TODO: implement."""
    raise NotImplementedError
