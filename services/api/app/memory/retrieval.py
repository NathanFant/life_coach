"""
Hybrid retrieval pipeline + token-budget assembler (docs/DESIGN.md §5.4).

Pipeline steps:
  1. ALWAYS-LOAD — core context that's always present (anti-RAG-failure measure)
  2. VECTOR RECALL — ANN search over embeddings filtered by user_id
  3. STRUCTURED RECALL — SQL for goals, tasks, stalled projects
  4. RANK + MMR — composite score + diversity selection
  5. BUDGET ASSEMBLER — fit within token_budget; always-load takes priority

The always-loaded block prevents the classic RAG failure of "the obvious fact
wasn't retrieved because the query phrasing didn't match the embedding."
"""

from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.ranking import (
    TYPE_HALF_LIFE_DAYS,
    composite_score,
    compute_decay,
    mmr_select,
)
from app.memory.service import ContextBundle, RetrievedMemory

logger = structlog.get_logger(__name__)

# Rough token estimate: 1 token ≈ 4 characters
_CHARS_PER_TOKEN = 4

# How many vector recall results to fetch before ranking (over-fetch then rank down)
_VECTOR_RECALL_LIMIT = 30

# After ranking, select this many via MMR before budget trimming
_MMR_K = 15


def _estimate_tokens(text_content: str) -> int:
    return max(1, len(text_content) // _CHARS_PER_TOKEN)


async def retrieve_context(
    db: AsyncSession,
    user_id: str,
    query: str,
    query_embedding: list[float] | None = None,
    *,
    token_budget: int = 3000,
) -> ContextBundle:
    """
    Assemble a ContextBundle for a coaching turn.

    query_embedding: pre-computed embedding of the user message.  If None,
                     vector recall is skipped (Phase 1 fallback; Phase 2 always embeds).
    """
    always = await _always_load(db, user_id)
    always_tokens = sum(_estimate_tokens(m.content) for m in always)
    remaining_budget = max(0, token_budget - always_tokens)

    recalled: list[RetrievedMemory] = []

    # Vector recall (skipped if no embedding provided in Phase 1)
    if query_embedding:
        recalled += await _vector_recall(db, user_id, query_embedding)

    # Structured recall (always runs — catches tasks, stalled projects, etc.)
    recalled += await _structured_recall(db, user_id)

    # Deduplicate by owner_id
    seen: set[str] = set()
    unique_recalled: list[RetrievedMemory] = []
    for m in recalled:
        if m.owner_id not in seen:
            seen.add(m.owner_id)
            unique_recalled.append(m)

    # Rank + MMR
    ranked = mmr_select(unique_recalled, k=_MMR_K, lambda_=0.5)

    # Budget trim: fill up to remaining_budget
    selected: list[RetrievedMemory] = []
    used = 0
    for m in ranked:
        tokens = _estimate_tokens(m.content)
        if used + tokens <= remaining_budget:
            selected.append(m)
            used += tokens
        else:
            break

    bundle = ContextBundle(
        always_loaded=always,
        recalled=selected,
        token_estimate=always_tokens + used,
    )
    logger.debug(
        "memory.retrieved",
        user_id=user_id,
        always_count=len(always),
        recalled_count=len(selected),
        token_estimate=bundle.token_estimate,
    )
    return bundle


# ─── Always-load queries ──────────────────────────────────────────────────────────


async def _always_load(db: AsyncSession, user_id: str) -> list[RetrievedMemory]:
    """
    Pull the core context that must always be present.

    1. life_profiles.summary + life_stage + attributes
    2. preferences (coaching/communication style)
    3. Top-5 active goals by importance
    4. Active projects (health, status)
    """
    memories: list[RetrievedMemory] = []

    # Life profile summary
    profile_row = await db.execute(
        text("""
            SELECT life_stage, summary, attributes
            FROM life_profiles WHERE user_id = :uid::uuid
        """),
        {"uid": user_id},
    )
    profile = profile_row.first()
    if profile:
        parts = []
        if profile[0]:
            parts.append(f"Life stage: {profile[0]}")
        if profile[1]:
            parts.append(f"Summary: {profile[1]}")
        if profile[2]:
            # Flatten key facts from attributes
            attrs = profile[2] if isinstance(profile[2], dict) else {}
            for k, v in list(attrs.items())[:10]:
                parts.append(f"{k}: {v}")
        if parts:
            memories.append(
                RetrievedMemory(
                    owner_type="semantic",
                    owner_id=f"{user_id}:profile",
                    content="\n".join(parts),
                    score=1.0,
                    metadata={"kind": "life_profile"},
                )
            )

    # Preferences
    pref_row = await db.execute(
        text("""
            SELECT communication_style, coaching_style, motivation_style
            FROM preferences WHERE user_id = :uid::uuid
        """),
        {"uid": user_id},
    )
    pref = pref_row.first()
    if pref and any(pref):
        pref_parts = []
        if pref[0]:
            pref_parts.append(f"Communication style: {pref[0]}")
        if pref[1]:
            pref_parts.append(f"Coaching style: {pref[1]}")
        if pref[2]:
            pref_parts.append(f"Motivation style: {pref[2]}")
        memories.append(
            RetrievedMemory(
                owner_type="semantic",
                owner_id=f"{user_id}:preferences",
                content="\n".join(pref_parts),
                score=1.0,
                metadata={"kind": "preferences"},
            )
        )

    # Active goals
    goals_row = await db.execute(
        text("""
            SELECT id, title, horizon, status, progress, importance
            FROM goals
            WHERE user_id = :uid::uuid AND status = 'active'
            ORDER BY importance DESC, created_at
            LIMIT 5
        """),
        {"uid": user_id},
    )
    for r in goals_row.fetchall():
        memories.append(
            RetrievedMemory(
                owner_type="goal",
                owner_id=str(r[0]),
                content=f"Goal ({r[2]}): {r[1]} — {r[4] * 100:.0f}% complete",
                score=1.0,
                metadata={"status": r[3], "importance": r[5]},
            )
        )

    # Active projects
    projects_row = await db.execute(
        text("""
            SELECT id, title, status, health
            FROM projects
            WHERE user_id = :uid::uuid AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 5
        """),
        {"uid": user_id},
    )
    for r in projects_row.fetchall():
        health_note = f" [{r[3]}]" if r[3] else ""
        memories.append(
            RetrievedMemory(
                owner_type="project",
                owner_id=str(r[0]),
                content=f"Project: {r[1]}{health_note}",
                score=1.0,
                metadata={"status": r[2], "health": r[3]},
            )
        )

    return memories


# ─── Vector recall ────────────────────────────────────────────────────────────────


async def _vector_recall(
    db: AsyncSession,
    user_id: str,
    query_embedding: list[float],
    limit: int = _VECTOR_RECALL_LIMIT,
) -> list[RetrievedMemory]:
    """ANN search over the embeddings table, filtered by user_id."""
    # Format the embedding as a Postgres vector literal
    vec_str = "[" + ",".join(f"{v:.6f}" for v in query_embedding) + "]"

    rows = await db.execute(
        text(f"""
            SELECT e.owner_type, e.owner_id::text, e.content, e.created_at,
                   1 - (e.embedding <=> '{vec_str}'::vector) AS similarity
            FROM embeddings e
            WHERE e.user_id = :uid::uuid
            ORDER BY e.embedding <=> '{vec_str}'::vector
            LIMIT :lim
        """),
        {"uid": user_id, "lim": limit},
    )

    memories: list[RetrievedMemory] = []
    for r in rows.fetchall():
        similarity = float(r[4])
        half_life = TYPE_HALF_LIFE_DAYS.get(r[0], 30.0)
        recency = compute_decay(r[3], half_life_days=half_life)
        score = composite_score(
            similarity=similarity,
            importance=0.5,  # default; override with actual importance if available
            recency=recency,
        )
        memories.append(
            RetrievedMemory(
                owner_type=r[0],
                owner_id=r[1],
                content=r[2],
                score=score,
                metadata={"similarity": similarity},
            )
        )

    return memories


# ─── Structured recall ────────────────────────────────────────────────────────────


async def _structured_recall(
    db: AsyncSession,
    user_id: str,
) -> list[RetrievedMemory]:
    """
    SQL-based recall for entities that shouldn't rely on vector similarity.

    Currently fetches:
      - Pending/doing tasks (due soon or overdue)
      - At-risk/stalled projects
      - Recent insights
    """
    memories: list[RetrievedMemory] = []

    # Pending / doing tasks
    tasks_row = await db.execute(
        text("""
            SELECT id, title, status, due_date
            FROM tasks
            WHERE user_id = :uid::uuid AND status IN ('todo', 'doing')
            ORDER BY due_date NULLS LAST, created_at
            LIMIT 10
        """),
        {"uid": user_id},
    )
    for r in tasks_row.fetchall():
        due = f" (due {r[3]})" if r[3] else ""
        memories.append(
            RetrievedMemory(
                owner_type="task",
                owner_id=str(r[0]),
                content=f"Task [{r[2]}]: {r[1]}{due}",
                score=0.7,  # tasks always surface — higher base score
                metadata={"status": r[2]},
            )
        )

    # At-risk / stalled projects
    stalled_row = await db.execute(
        text("""
            SELECT id, title, health
            FROM projects
            WHERE user_id = :uid::uuid AND health IN ('at_risk', 'stalled')
            LIMIT 5
        """),
        {"uid": user_id},
    )
    for r in stalled_row.fetchall():
        memories.append(
            RetrievedMemory(
                owner_type="project",
                owner_id=str(r[0]),
                content=f"⚠ Project at risk: {r[1]} ({r[2]})",
                score=0.8,
                metadata={"health": r[2]},
            )
        )

    # Recent insights
    insights_row = await db.execute(
        text("""
            SELECT id, content, importance, created_at
            FROM insights
            WHERE user_id = :uid::uuid
            ORDER BY created_at DESC
            LIMIT 5
        """),
        {"uid": user_id},
    )
    for r in insights_row.fetchall():
        recency = compute_decay(r[3], half_life_days=180)
        importance_norm = (r[2] or 3) / 5.0
        score = composite_score(similarity=0.5, importance=importance_norm, recency=recency)
        memories.append(
            RetrievedMemory(
                owner_type="insight",
                owner_id=str(r[0]),
                content=r[1],
                score=score,
                metadata={"importance": r[2]},
            )
        )

    return memories
