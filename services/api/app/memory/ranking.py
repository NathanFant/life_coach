"""
Composite memory ranking + MMR diversity selection (docs/DESIGN.md §5.3).

Composite score formula:
    score = w_sim · similarity
          + w_imp · importance_norm
          + w_rec · recency_decay
          - w_red · redundancy (applied by MMR)

Weights are dataclass fields — tune via the eval harness (§6.6), not guessed forever.

MMR (Maximal Marginal Relevance):
    Selects diverse results by penalising candidates that are semantically similar
    to already-selected items.  Lambda controls the relevance/diversity trade-off:
      λ=1.0 → pure relevance ranking
      λ=0.0 → pure diversity
      λ=0.5 → balanced (recommended default)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.memory.service import RetrievedMemory


@dataclass(frozen=True)
class RankWeights:
    similarity: float = 0.45
    importance: float = 0.25
    recency: float = 0.30


def composite_score(
    similarity: float,
    importance: float,
    recency: float,
    *,
    weights: RankWeights | None = None,
    access_boost: float = 0.0,
) -> float:
    """
    Compute a composite retrieval score in [0, ∞).

    All inputs are expected to be in [0, 1].
    access_boost is a small additive bonus for frequently-accessed memories.
    """
    w = weights or RankWeights()
    return (
        w.similarity * similarity + w.importance * importance + w.recency * recency + access_boost
    )


# Per-type recency half-life (days).  Active goals/projects use a very long
# half-life so they never effectively decay while status == 'active'.
TYPE_HALF_LIFE_DAYS: dict[str, float] = {
    "episodic": 30.0,
    "semantic": 365.0,
    "insight": 180.0,
    "goal": 3650.0,  # 10 years — effectively no decay for active goals
    "project": 3650.0,
    "message": 14.0,
}


def compute_decay(
    created_at: datetime,
    *,
    half_life_days: float = 30.0,
) -> float:
    """
    Exponential recency decay: exp(-Δt / τ).

    Returns 1.0 for just-created memories and approaches 0.0 asymptotically.
    τ = half_life_days / ln(2) so that after `half_life_days` the value is 0.5.
    """
    now = datetime.now(UTC)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    delta_days = max(0.0, (now - created_at).total_seconds() / 86400)
    tau = half_life_days / math.log(2)
    return math.exp(-delta_days / tau)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Fast cosine similarity for two equal-length float lists."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def mmr_select(
    candidates: list[RetrievedMemory],
    k: int,
    lambda_: float = 0.5,
) -> list[RetrievedMemory]:
    """
    Maximal Marginal Relevance selection.

    Iteratively picks the candidate that maximises:
        λ · score(candidate) - (1 - λ) · max_sim_to_selected

    where max_sim_to_selected is the cosine similarity to the most similar
    already-selected item.  Requires RetrievedMemory.embedding to be set.

    Candidates without embeddings fall back to score-only ranking (MMR penalty = 0).
    """
    if not candidates:
        return []
    k = min(k, len(candidates))
    remaining = list(candidates)
    selected: list[RetrievedMemory] = []

    # First pick: highest composite score
    remaining.sort(key=lambda m: m.score, reverse=True)
    selected.append(remaining.pop(0))

    while len(selected) < k and remaining:
        best: RetrievedMemory | None = None
        best_mmr = float("-inf")

        for candidate in remaining:
            relevance = lambda_ * candidate.score

            # Compute similarity to the most similar already-selected item
            if candidate.embedding and any(s.embedding for s in selected):
                max_sim = max(
                    _cosine_similarity(candidate.embedding, s.embedding)
                    for s in selected
                    if s.embedding
                )
                diversity = (1 - lambda_) * max_sim
            else:
                diversity = 0.0

            mmr_score = relevance - diversity
            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best = candidate

        if best is not None:
            selected.append(best)
            remaining.remove(best)

    return selected
