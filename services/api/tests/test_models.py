"""
Unit tests for all SQLAlchemy ORM models.

Tests verify:
  - All models import and have the correct table name
  - Primary key and required columns exist
  - Relationships are declared (foreign key columns present)
  - Soft-delete / temporal columns are present where required
  - pgvector column type is present on embeddings
  - Audit table is append-only by convention (no updated_at)

These are pure-Python schema tests — no database connection required.
"""

import pytest
from sqlalchemy import inspect as sa_inspect

from app.db.models import (
    AuditEvent,
    Conversation,
    Domain,
    Embedding,
    EpisodicMemory,
    Goal,
    Insight,
    LifeProfile,
    Message,
    Milestone,
    Preference,
    Project,
    Relationship,
    SemanticFact,
    Task,
    TimelineEvent,
    User,
)

# ─── Helpers ────────────────────────────────────────────────────────────────────


def col_names(model: type) -> set[str]:
    return {c.key for c in sa_inspect(model).mapper.column_attrs}


# ─── User ───────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestUserModel:
    def test_table_name(self) -> None:
        assert User.__tablename__ == "users"

    def test_required_columns(self) -> None:
        cols = col_names(User)
        assert {
            "id",
            "external_auth_id",
            "email",
            "status",
            "onboarding_state",
            "consent",
            "created_at",
            "updated_at",
        }.issubset(cols)

    def test_soft_delete(self) -> None:
        assert "deleted_at" in col_names(User)

    def test_pk_is_uuid(self) -> None:
        pk = sa_inspect(User).mapper.primary_key[0]
        assert "uuid" in str(pk.type).lower()


# ─── LifeProfile ─────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestLifeProfileModel:
    def test_table_name(self) -> None:
        assert LifeProfile.__tablename__ == "life_profiles"

    def test_required_columns(self) -> None:
        cols = col_names(LifeProfile)
        assert {"id", "user_id", "completeness", "version", "created_at", "updated_at"}.issubset(
            cols
        )

    def test_has_user_fk(self) -> None:
        assert "user_id" in col_names(LifeProfile)


# ─── Domain ──────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestDomainModel:
    def test_table_name(self) -> None:
        assert Domain.__tablename__ == "domains"

    def test_required_columns(self) -> None:
        cols = col_names(Domain)
        assert {"id", "user_id", "kind", "priority", "created_at", "updated_at"}.issubset(cols)

    def test_desired_state_columns(self) -> None:
        cols = col_names(Domain)
        assert {"desired_1y", "desired_5y", "current_state"}.issubset(cols)


# ─── Conversation + Message ───────────────────────────────────────────────────────


@pytest.mark.unit
class TestConversationModel:
    def test_table_name(self) -> None:
        assert Conversation.__tablename__ == "conversations"

    def test_required_columns(self) -> None:
        cols = col_names(Conversation)
        assert {"id", "user_id", "kind", "created_at", "updated_at"}.issubset(cols)


@pytest.mark.unit
class TestMessageModel:
    def test_table_name(self) -> None:
        assert Message.__tablename__ == "messages"

    def test_required_columns(self) -> None:
        cols = col_names(Message)
        assert {"id", "conversation_id", "user_id", "role", "content", "created_at"}.issubset(cols)

    def test_has_token_and_model_columns(self) -> None:
        cols = col_names(Message)
        assert {"tokens", "model", "tool_calls"}.issubset(cols)


# ─── Goal ─────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestGoalModel:
    def test_table_name(self) -> None:
        assert Goal.__tablename__ == "goals"

    def test_required_columns(self) -> None:
        cols = col_names(Goal)
        assert {
            "id",
            "user_id",
            "title",
            "horizon",
            "status",
            "progress",
            "importance",
            "created_at",
            "updated_at",
        }.issubset(cols)


# ─── Project + Milestone + Task ──────────────────────────────────────────────────


@pytest.mark.unit
class TestProjectModel:
    def test_table_name(self) -> None:
        assert Project.__tablename__ == "projects"

    def test_required_columns(self) -> None:
        cols = col_names(Project)
        assert {"id", "user_id", "title", "status", "health", "created_at", "updated_at"}.issubset(
            cols
        )


@pytest.mark.unit
class TestMilestoneModel:
    def test_table_name(self) -> None:
        assert Milestone.__tablename__ == "milestones"

    def test_required_columns(self) -> None:
        assert {"id", "user_id", "project_id", "title", "status"}.issubset(col_names(Milestone))


@pytest.mark.unit
class TestTaskModel:
    def test_table_name(self) -> None:
        assert Task.__tablename__ == "tasks"

    def test_required_columns(self) -> None:
        assert {"id", "user_id", "title", "status", "source"}.issubset(col_names(Task))


# ─── Relationship + Timeline + Insight ───────────────────────────────────────────


@pytest.mark.unit
class TestRelationshipModel:
    def test_table_name(self) -> None:
        assert Relationship.__tablename__ == "relationships"

    def test_required_columns(self) -> None:
        assert {"id", "user_id", "role", "importance"}.issubset(col_names(Relationship))


@pytest.mark.unit
class TestTimelineEventModel:
    def test_table_name(self) -> None:
        assert TimelineEvent.__tablename__ == "timeline_events"

    def test_required_columns(self) -> None:
        cols = col_names(TimelineEvent)
        assert {"id", "user_id", "title", "is_anticipated"}.issubset(cols)


@pytest.mark.unit
class TestInsightModel:
    def test_table_name(self) -> None:
        assert Insight.__tablename__ == "insights"

    def test_required_columns(self) -> None:
        assert {"id", "user_id", "kind", "content", "importance"}.issubset(col_names(Insight))


# ─── Memory tables ────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestSemanticFactModel:
    def test_table_name(self) -> None:
        assert SemanticFact.__tablename__ == "semantic_facts"

    def test_versioning_columns(self) -> None:
        cols = col_names(SemanticFact)
        # Temporal belief revision (docs/DESIGN.md §5.5)
        assert {"valid_from", "valid_to", "superseded_by", "confidence", "source"}.issubset(cols)

    def test_required_columns(self) -> None:
        assert {"id", "user_id", "predicate", "value"}.issubset(col_names(SemanticFact))


@pytest.mark.unit
class TestEpisodicMemoryModel:
    def test_table_name(self) -> None:
        assert EpisodicMemory.__tablename__ == "episodic_memories"

    def test_ranking_columns(self) -> None:
        cols = col_names(EpisodicMemory)
        # Columns used by the ranking formula (docs/DESIGN.md §5.3)
        assert {"salience", "access_count", "last_accessed_at", "decay_score"}.issubset(cols)


# ─── Embedding ─────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestEmbeddingModel:
    def test_table_name(self) -> None:
        assert Embedding.__tablename__ == "embeddings"

    def test_polymorphic_columns(self) -> None:
        cols = col_names(Embedding)
        # Polymorphic index points at any retrievable entity (docs/DESIGN.md §4.2)
        assert {"owner_type", "owner_id", "content", "model"}.issubset(cols)

    def test_has_vector_column(self) -> None:
        cols = col_names(Embedding)
        assert "embedding" in cols


# ─── Preference ──────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestPreferenceModel:
    def test_table_name(self) -> None:
        assert Preference.__tablename__ == "preferences"

    def test_coaching_style_columns(self) -> None:
        cols = col_names(Preference)
        assert {"communication_style", "coaching_style", "motivation_style"}.issubset(cols)


# ─── Audit ─────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestAuditEventModel:
    def test_table_name(self) -> None:
        assert AuditEvent.__tablename__ == "audit_events"

    def test_append_only_shape(self) -> None:
        cols = col_names(AuditEvent)
        # Audit is append-only — no updated_at (docs/DESIGN.md §4.6)
        assert "updated_at" not in cols
        assert {"id", "actor", "action", "created_at"}.issubset(cols)
