"""Consolidation / "sleep" jobs (docs/DESIGN.md §5.6).

Scheduled (Celery Beat): episodic clustering→distillation, decay & prune,
reflection generation, profile re-summarization, embedding-model migration.
"""

# TODO (Phase 2): background-only; never auto-deletes structured entities.
