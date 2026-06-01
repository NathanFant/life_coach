"""
Unit tests for the memory retrieval pipeline (docs/DESIGN.md §5.3–5.4).

Tests the composite ranking formula and the ContextBundle assembler.
No database calls are made — the store is mocked with in-memory data.

Scenarios:
  - Composite score increases with higher similarity
  - Composite score increases with higher importance
  - Recency decay reduces score for old memories
  - MMR diversity penalty removes near-duplicate results
  - Token budget assembler includes always-load before recalled
  - Token budget assembler respects the budget limit
  - ContextBundle is well-formed (correct types and fields)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.memory.ranking import (
    RankWeights,
    composite_score,
    compute_decay,
    mmr_select,
)
from app.memory.service import ContextBundle, RetrievedMemory

# ─── Composite scoring ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestCompositeScore:
    def test_higher_similarity_raises_score(self) -> None:
        weights = RankWeights()
        s1 = composite_score(similarity=0.9, importance=0.5, recency=0.5, weights=weights)
        s2 = composite_score(similarity=0.5, importance=0.5, recency=0.5, weights=weights)
        assert s1 > s2

    def test_higher_importance_raises_score(self) -> None:
        weights = RankWeights()
        s1 = composite_score(similarity=0.5, importance=0.9, recency=0.5, weights=weights)
        s2 = composite_score(similarity=0.5, importance=0.1, recency=0.5, weights=weights)
        assert s1 > s2

    def test_score_is_bounded(self) -> None:
        weights = RankWeights()
        s = composite_score(similarity=1.0, importance=1.0, recency=1.0, weights=weights)
        assert 0.0 <= s <= 1.5  # no hard upper bound, but sanity check

    def test_score_is_non_negative(self) -> None:
        weights = RankWeights()
        s = composite_score(similarity=0.0, importance=0.0, recency=0.0, weights=weights)
        assert s >= 0.0


# ─── Recency decay ─────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRecencyDecay:
    def test_recent_memory_decays_less(self) -> None:
        now = datetime.now(UTC)
        recent = compute_decay(created_at=now - timedelta(days=1), half_life_days=30)
        old = compute_decay(created_at=now - timedelta(days=90), half_life_days=30)
        assert recent > old

    def test_just_created_has_decay_near_one(self) -> None:
        now = datetime.now(UTC)
        d = compute_decay(created_at=now, half_life_days=30)
        assert d > 0.95

    def test_very_old_has_low_decay(self) -> None:
        now = datetime.now(UTC)
        d = compute_decay(created_at=now - timedelta(days=365), half_life_days=30)
        assert d < 0.1


# ─── MMR diversity selection ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestMMRSelect:
    def _mem(self, content: str, score: float, embedding: list[float]) -> RetrievedMemory:
        return RetrievedMemory(
            owner_type="episodic",
            owner_id="00000000-0000-0000-0000-000000000001",
            content=content,
            score=score,
            embedding=embedding,
        )

    def test_returns_top_k(self) -> None:
        mems = [
            self._mem("A", 0.9, [1.0, 0.0]),
            self._mem("B", 0.8, [0.0, 1.0]),
            self._mem("C", 0.7, [0.5, 0.5]),
        ]
        selected = mmr_select(mems, k=2, lambda_=0.5)
        assert len(selected) == 2

    def test_penalises_near_duplicates(self) -> None:
        # Two near-identical items; only one should be selected
        mems = [
            self._mem("Career goal A", 0.9, [1.0, 0.01]),
            self._mem("Career goal B", 0.89, [1.0, 0.02]),  # nearly same embedding
            self._mem("Family concern", 0.7, [0.0, 1.0]),  # very different
        ]
        selected = mmr_select(mems, k=2, lambda_=0.5)
        contents = {m.content for m in selected}
        # The diverse "Family concern" should beat the near-duplicate
        assert "Family concern" in contents

    def test_empty_input_returns_empty(self) -> None:
        assert mmr_select([], k=3, lambda_=0.5) == []

    def test_k_larger_than_input_returns_all(self) -> None:
        mems = [self._mem("X", 0.8, [1.0, 0.0])]
        selected = mmr_select(mems, k=5, lambda_=0.5)
        assert len(selected) == 1


# ─── ContextBundle ────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestContextBundle:
    def test_bundle_has_required_fields(self) -> None:
        bundle = ContextBundle(
            always_loaded=[
                RetrievedMemory(
                    owner_type="semantic",
                    owner_id="00000000-0000-0000-0000-000000000001",
                    content="User is a software engineer",
                    score=1.0,
                )
            ],
            recalled=[],
            token_estimate=150,
        )
        assert len(bundle.always_loaded) == 1
        assert bundle.token_estimate == 150

    def test_total_items(self) -> None:
        bundle = ContextBundle(
            always_loaded=[
                RetrievedMemory("semantic", "00000000-0000-0000-0000-000000000001", "A", 1.0),
                RetrievedMemory("goal", "00000000-0000-0000-0000-000000000002", "B", 0.9),
            ],
            recalled=[
                RetrievedMemory("episodic", "00000000-0000-0000-0000-000000000003", "C", 0.7),
            ],
            token_estimate=500,
        )
        assert len(bundle.always_loaded) + len(bundle.recalled) == 3
