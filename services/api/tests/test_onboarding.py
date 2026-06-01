"""
Unit tests for the adaptive onboarding engine (docs/DESIGN.md §2.3).

The onboarding engine is a hybrid: a deterministic question graph governs
coverage and slot-filling order; an LLM phrases questions and evaluates answers.

Tests cover:
  - QuestionGraph: next question for an empty profile
  - QuestionGraph: branches based on answer (e.g. "have kids" → parenting slots)
  - QuestionGraph: skips irrelevant domains
  - SlotSchema: completeness score increases as slots are filled
  - SlotSchema: minimum completeness to consider onboarding "done"
  - OnboardingEngine: routes to the correct next question
  - OnboardingEngine: produces a LifeProfile snapshot after completion
  - OnboardingEngine: is resumable (state serialises/deserialises)
"""

from __future__ import annotations

import pytest

from app.onboarding.engine import (
    DomainSlot,
    OnboardingState,
    QuestionGraph,
    SlotSchema,
    build_initial_state,
)

# ─── QuestionGraph ────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestQuestionGraph:
    def test_first_question_is_always_returned(self) -> None:
        graph = QuestionGraph()
        state = build_initial_state()
        q = graph.next_question(state)
        assert q is not None
        assert q.slot is not None
        assert len(q.text) > 0

    def test_no_question_when_all_slots_filled(self) -> None:
        graph = QuestionGraph()
        state = build_initial_state()
        # Set branching conditions first so conditional slots get auto-skipped
        state.schema.mark_filled(DomainSlot.HAS_CHILDREN, {"value": False})
        state.schema.mark_filled(DomainSlot.EMPLOYMENT_STATUS, {"value": "employed"})
        state.schema.mark_filled(DomainSlot.HAS_SIDE_PROJECT, {"value": False})
        # Fill the remaining mandatory slots
        for slot in state.schema.mandatory_slots():
            if not state.schema.is_filled(slot):
                state.schema.mark_filled(slot, {"value": "answered"})
        q = graph.next_question(state)
        assert q is None

    def test_skips_parenting_slots_when_no_children(self) -> None:
        graph = QuestionGraph()
        state = build_initial_state()
        state.schema.mark_filled(DomainSlot.HAS_CHILDREN, {"value": False})
        # Parenting questions should not be surfaced
        state.schema.mark_filled(DomainSlot.EMPLOYMENT_STATUS, {"value": "employed"})
        state.schema.mark_filled(DomainSlot.RELATIONSHIP_STATUS, {"value": "single"})
        for _ in range(20):
            q = graph.next_question(state)
            if q is None:
                break
            assert q.slot != DomainSlot.PARENTING_STYLE
            state.schema.mark_filled(q.slot, {"value": "answered"})

    def test_branches_into_entrepreneurship_when_building_business(self) -> None:
        graph = QuestionGraph()
        state = build_initial_state()
        state.schema.mark_filled(DomainSlot.EMPLOYMENT_STATUS, {"value": "building_business"})
        # Next questions should include business-specific slots
        slots_seen = set()
        for _ in range(10):
            q = graph.next_question(state)
            if q is None:
                break
            slots_seen.add(q.slot)
            state.schema.mark_filled(q.slot, {"value": "answered"})
        assert DomainSlot.BUSINESS_STAGE in slots_seen or DomainSlot.BUSINESS_REVENUE in slots_seen


# ─── SlotSchema ────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestSlotSchema:
    def test_completeness_starts_at_zero(self) -> None:
        schema = SlotSchema()
        assert schema.completeness() == 0.0

    def test_completeness_increases_on_fill(self) -> None:
        schema = SlotSchema()
        schema.mark_filled(DomainSlot.EMPLOYMENT_STATUS, {"value": "employed"})
        assert schema.completeness() > 0.0

    def test_completeness_reaches_one_when_all_mandatory_filled(self) -> None:
        schema = SlotSchema()
        for slot in schema.mandatory_slots():
            schema.mark_filled(slot, {"value": "answered"})
        assert schema.completeness() >= 1.0

    def test_filled_slots_are_retrievable(self) -> None:
        schema = SlotSchema()
        schema.mark_filled(DomainSlot.AGE_RANGE, {"value": "30s"})
        assert schema.get_value(DomainSlot.AGE_RANGE) == {"value": "30s"}

    def test_unfilled_slot_returns_none(self) -> None:
        schema = SlotSchema()
        assert schema.get_value(DomainSlot.AGE_RANGE) is None

    def test_mandatory_slots_is_not_empty(self) -> None:
        schema = SlotSchema()
        assert len(schema.mandatory_slots()) >= 5


# ─── OnboardingState ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestOnboardingState:
    def test_build_initial_state(self) -> None:
        state = build_initial_state()
        assert state.schema.completeness() == 0.0
        assert state.is_complete() is False

    def test_serialise_and_deserialise(self) -> None:
        state = build_initial_state()
        state.schema.mark_filled(DomainSlot.EMPLOYMENT_STATUS, {"value": "employed"})
        payload = state.to_dict()
        restored = OnboardingState.from_dict(payload)
        assert restored.schema.get_value(DomainSlot.EMPLOYMENT_STATUS) == {"value": "employed"}

    def test_is_complete_when_threshold_met(self) -> None:
        state = build_initial_state()
        for slot in state.schema.mandatory_slots():
            state.schema.mark_filled(slot, {"value": "answered"})
        assert state.is_complete() is True
