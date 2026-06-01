"""
Unit tests for the Alembic migration.

Validates the migration module structure without requiring a running database.
Integration tests that actually execute the migration against Postgres are
marked @pytest.mark.integration and require docker-compose services.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_migration(name: str) -> ModuleType:
    """Load a migration file by name without executing it."""
    path = Path(__file__).parent.parent / "migrations" / "versions" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.mark.unit
class TestInitialSchemaMigration:
    def test_module_loads(self) -> None:
        m = _load_migration("0001_initial_schema")
        assert m is not None

    def test_has_revision(self) -> None:
        m = _load_migration("0001_initial_schema")
        assert m.revision == "0001"

    def test_down_revision_is_none(self) -> None:
        m = _load_migration("0001_initial_schema")
        assert m.down_revision is None

    def test_upgrade_is_callable(self) -> None:
        m = _load_migration("0001_initial_schema")
        assert callable(m.upgrade)

    def test_downgrade_is_callable(self) -> None:
        m = _load_migration("0001_initial_schema")
        assert callable(m.downgrade)

    def test_rls_tables_list_is_complete(self) -> None:
        m = _load_migration("0001_initial_schema")
        required = {
            "life_profiles",
            "domains",
            "conversations",
            "messages",
            "coaching_sessions",
            "goals",
            "projects",
            "milestones",
            "tasks",
            "relationships",
            "timeline_events",
            "insights",
            "semantic_facts",
            "episodic_memories",
            "preferences",
            "embeddings",
        }
        assert required == set(m._RLS_TABLES)
