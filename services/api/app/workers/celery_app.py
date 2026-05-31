"""Celery app — async memory/consolidation/nudge jobs (docs/DESIGN.md §3.1, §5.6).

Runs as separate processes from the API; communicates only via Redis + Postgres.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "life_coach",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)

# Celery Beat schedules (consolidation, reflections, scheduled check-ins) added in Phase 2.
celery_app.conf.beat_schedule = {}
