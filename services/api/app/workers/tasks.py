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

    Extracts structured memory from a coaching session and stores it in the database.
    Idempotent on (user_id, session_id) because extraction is keyed by session_id.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from app.core.config import get_settings
    from app.llm.litellm_client import LiteLLMCoachLLM
    from app.memory.extraction import extract_from_session
    import asyncio
    import uuid

    settings = get_settings()

    # Create a synchronous database session
    engine = create_engine(settings.database_url.replace("psycopg://", "postgresql://"))

    try:
        with Session(engine) as db:
            # Run the async extraction in an event loop
            llm = LiteLLMCoachLLM(model=settings.extraction_model)

            # Convert to sync by running in a new event loop
            try:
                extracted = asyncio.run(extract_from_session(user_id, session_id, llm, db))
            except RuntimeError:
                # If an event loop already exists, create a task
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    extracted = loop.run_until_complete(extract_from_session(user_id, session_id, llm, db))
                finally:
                    loop.close()

            if not extracted:
                logger.info("extraction.no_data", user_id=user_id, session_id=session_id)
                return

            # Store semantic facts
            _store_semantic_facts(db, user_id, session_id, extracted.get("semantic_facts", []))

            # Store insights
            _store_insights(db, user_id, session_id, extracted.get("insights", []))

            # Store episodic memory
            if extracted.get("episodic_summary"):
                _store_episodic_memory(db, user_id, session_id, extracted["episodic_summary"])

            # Store goals
            _store_goals(db, user_id, extracted.get("goals", []))

            # Generate embeddings for new entities
            _embed_new_entities(db, user_id, session_id, llm)

            db.commit()
            logger.info("extraction.stored", user_id=user_id, session_id=session_id)

    finally:
        engine.dispose()


def _store_semantic_facts(db: Session, user_id: str, session_id: str, facts: list[dict]) -> None:
    """Store semantic facts with deduplication."""
    from sqlalchemy import text
    from datetime import datetime

    for fact in facts:
        predicate = fact.get("predicate")
        value = fact.get("value")
        confidence = fact.get("confidence", 0.7)

        if not predicate or value is None:
            continue

        # Check if a current fact with this predicate exists
        existing = db.execute(
            text("""
                SELECT id FROM semantic_facts
                WHERE user_id = :uid::uuid AND predicate = :pred AND valid_to IS NULL
            """),
            {"uid": user_id, "pred": predicate},
        ).first()

        if existing:
            # Supersede the old fact
            old_id = existing[0]
            new_id = str(__import__("uuid").uuid4())
            db.execute(
                text("""
                    UPDATE semantic_facts
                    SET valid_to = NOW(), superseded_by = :nid::uuid
                    WHERE id = :oid::uuid
                """),
                {"nid": new_id, "oid": old_id},
            )
            db.execute(
                text("""
                    INSERT INTO semantic_facts
                    (id, user_id, predicate, value, confidence, source, source_ref, valid_from)
                    VALUES (:id::uuid, :uid::uuid, :pred, :val::jsonb, :conf, :src, :ref::uuid, NOW())
                """),
                {
                    "id": new_id,
                    "uid": user_id,
                    "pred": predicate,
                    "val": __import__("json").dumps(value),
                    "conf": confidence,
                    "src": "message",
                    "ref": session_id,
                },
            )
        else:
            # Insert new fact
            db.execute(
                text("""
                    INSERT INTO semantic_facts
                    (id, user_id, predicate, value, confidence, source, source_ref, valid_from)
                    VALUES (:id::uuid, :uid::uuid, :pred, :val::jsonb, :conf, :src, :ref::uuid, NOW())
                """),
                {
                    "id": str(__import__("uuid").uuid4()),
                    "uid": user_id,
                    "pred": predicate,
                    "val": __import__("json").dumps(value),
                    "conf": confidence,
                    "src": "message",
                    "ref": session_id,
                },
            )


def _store_insights(db: Session, user_id: str, session_id: str, insights: list[dict]) -> None:
    """Store coaching insights."""
    from sqlalchemy import text
    import uuid

    for insight in insights:
        content = insight.get("content")
        kind = insight.get("kind", "coaching-note")
        importance = insight.get("importance", 3)

        if not content:
            continue

        db.execute(
            text("""
                INSERT INTO insights (id, user_id, session_id, kind, content, importance)
                VALUES (:id::uuid, :uid::uuid, :sid::uuid, :kind, :content, :imp)
            """),
            {
                "id": str(uuid.uuid4()),
                "uid": user_id,
                "sid": session_id,
                "kind": kind,
                "content": content,
                "imp": importance,
            },
        )


def _store_episodic_memory(db: Session, user_id: str, session_id: str, summary: str) -> None:
    """Store episodic memory from the session."""
    from sqlalchemy import text
    import uuid

    db.execute(
        text("""
            INSERT INTO episodic_memories (id, user_id, session_id, summary, salience)
            VALUES (:id::uuid, :uid::uuid, :sid::uuid, :summary, :sal)
        """),
        {
            "id": str(uuid.uuid4()),
            "uid": user_id,
            "sid": session_id,
            "summary": summary,
            "sal": 0.7,
        },
    )


def _store_goals(db: Session, user_id: str, goals: list[dict]) -> None:
    """Store extracted goals."""
    from sqlalchemy import text
    import uuid

    for goal in goals:
        title = goal.get("title")
        horizon = goal.get("horizon", "short")
        description = goal.get("description")

        if not title:
            continue

        db.execute(
            text("""
                INSERT INTO goals (id, user_id, title, description, horizon, status, importance)
                VALUES (:id::uuid, :uid::uuid, :title, :desc, :horizon, :status, :imp)
            """),
            {
                "id": str(uuid.uuid4()),
                "uid": user_id,
                "title": title,
                "desc": description,
                "horizon": horizon,
                "status": "active",
                "imp": 3,
            },
        )


def _embed_new_entities(db: Session, user_id: str, session_id: str, llm) -> None:
    """Generate embeddings for new semantic facts and insights."""
    from sqlalchemy import text
    import uuid
    import asyncio

    # Fetch new semantic facts (those created in this extraction)
    facts = db.execute(
        text("""
            SELECT id, predicate, value FROM semantic_facts
            WHERE user_id = :uid::uuid AND source_ref = :ref::uuid
        """),
        {"uid": user_id, "ref": session_id},
    ).fetchall()

    # Fetch new insights
    insights = db.execute(
        text("""
            SELECT id, content FROM insights
            WHERE user_id = :uid::uuid AND session_id = :sid::uuid
        """),
        {"uid": user_id, "sid": session_id},
    ).fetchall()

    if not facts and not insights:
        return

    # Collect texts to embed
    texts_to_embed = []
    entity_map = []  # Track which text maps to which entity

    for fact_id, predicate, value in facts:
        text_content = f"{predicate}: {value}"
        texts_to_embed.append(text_content)
        entity_map.append(("semantic", fact_id, text_content))

    for insight_id, content in insights:
        texts_to_embed.append(content)
        entity_map.append(("insight", insight_id, content))

    if not texts_to_embed:
        return

    # Generate embeddings (need to run async in sync context)
    try:
        embeddings = asyncio.run(llm.embed(texts_to_embed))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            embeddings = loop.run_until_complete(llm.embed(texts_to_embed))
        finally:
            loop.close()

    # Store embeddings
    for (owner_type, owner_id, content), embedding in zip(entity_map, embeddings):
        db.execute(
            text("""
                INSERT INTO embeddings (id, user_id, owner_type, owner_id, model, content, embedding)
                VALUES (:id::uuid, :uid::uuid, :otype, :oid::uuid, :model, :content, :emb::vector)
            """),
            {
                "id": str(uuid.uuid4()),
                "uid": user_id,
                "otype": owner_type,
                "oid": owner_id,
                "model": "openai/text-embedding-3-small",
                "content": content,
                "emb": embedding,
            },
        )


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
