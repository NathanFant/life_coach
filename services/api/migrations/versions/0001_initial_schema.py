"""Initial schema: all life-coach tables, pgvector, RLS, and indexes.

Revision ID: 0001
Revises:
Create Date: 2026-05-31

What this migration does
------------------------
1. Enables the pgvector extension (requires Postgres 15+, pgvector installed).
2. Creates all life-model tables in dependency order.
3. Creates all indexes including the HNSW vector index on embeddings.
4. Enables Row-Level Security on every user-owned table and attaches a
   permissive policy so the app role can only see rows where
   user_id = current_setting('app.user_id')::uuid.
5. Creates monthly partitions for messages and audit_events (initial 3 months).

Security note
-------------
RLS is defence-in-depth.  The API service also enforces ownership in the service
layer (docs/DESIGN.md §7.4).  The DB role 'coach_app' must not have BYPASSRLS.

Rolling forward
---------------
Run via: uv run alembic upgrade head
Rolling back: uv run alembic downgrade -1
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

# Tables that carry user-owned data and need RLS
_RLS_TABLES = [
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
]


def upgrade() -> None:
    # ── 0. Extensions ─────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")  # gen_random_uuid()

    # ── 1. users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_auth_id", sa.String(256), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("display_name", sa.Text, nullable=True),
        sa.Column("locale", sa.String(10), nullable=False, server_default="en"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("onboarding_state", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("consent", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_external_auth_id", "users", ["external_auth_id"])
    op.create_index("ix_users_status", "users", ["status"])

    # ── 2. life_profiles ──────────────────────────────────────────────────────
    op.create_table(
        "life_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("life_stage", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("attributes", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("completeness", sa.Float, nullable=False, server_default="0"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_life_profiles_user_id", "life_profiles", ["user_id"])

    # ── 3. domains ────────────────────────────────────────────────────────────
    op.create_table(
        "domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("current_state", sa.Text, nullable=True),
        sa.Column("desired_1y", sa.Text, nullable=True),
        sa.Column("desired_5y", sa.Text, nullable=True),
        sa.Column("obstacles", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("strengths", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["life_profile_id"], ["life_profiles.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "kind", name="uq_domains_user_kind"),
    )
    op.create_index("ix_domains_user_id", "domains", ["user_id"])
    op.create_index("ix_domains_user_kind", "domains", ["user_id", "kind"])

    # ── 4. conversations ──────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("kind", sa.Text, nullable=False, server_default="coaching"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conversations_user_id_updated", "conversations", ["user_id", "updated_at"])

    # ── 5. coaching_sessions ──────────────────────────────────────────────────
    op.create_table(
        "coaching_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("focus_domain", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("detected_changes", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("outcome_actions", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("sentiment", postgresql.JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_coaching_sessions_user_id", "coaching_sessions", ["user_id"])
    op.create_index("ix_coaching_sessions_started_at", "coaching_sessions",
                    ["user_id", "started_at"])

    # ── 6. messages (parent table — partitioned by month) ─────────────────────
    op.execute("""
        CREATE TABLE messages (
            id          uuid NOT NULL DEFAULT gen_random_uuid(),
            conversation_id uuid NOT NULL,
            user_id     uuid NOT NULL,
            role        text NOT NULL,
            content     text NOT NULL,
            tokens      integer,
            model       text,
            tool_calls  jsonb,
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)
    op.execute("""
        ALTER TABLE messages
            ADD CONSTRAINT fk_messages_conversation
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE messages
            ADD CONSTRAINT fk_messages_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    """)
    # Create initial monthly partitions (3 months from scaffold date)
    for ym_start, ym_end in [
        ("2026-05-01", "2026-06-01"),
        ("2026-06-01", "2026-07-01"),
        ("2026-07-01", "2026-08-01"),
    ]:
        safe = ym_start.replace("-", "_")
        op.execute(f"""
            CREATE TABLE messages_{safe}
            PARTITION OF messages
            FOR VALUES FROM ('{ym_start}') TO ('{ym_end}')
        """)
    op.create_index("ix_messages_conversation_created", "messages",
                    ["conversation_id", "created_at"])
    op.create_index("ix_messages_user_id", "messages", ["user_id"])

    # ── 7. goals ──────────────────────────────────────────────────────────────
    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("horizon", sa.Text, nullable=False),
        sa.Column("target_date", sa.Date, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column("progress", sa.Float, nullable=False, server_default="0"),
        sa.Column("importance", sa.Integer, nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["domain_id"], ["domains.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_goals_user_status_importance", "goals",
                    ["user_id", "status", "importance"])

    # ── 8. projects ───────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column("health", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_projects_user_status", "projects", ["user_id", "status"])

    # ── 9. milestones ─────────────────────────────────────────────────────────
    op.create_table(
        "milestones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_milestones_project_id", "milestones", ["project_id"])
    op.create_index("ix_milestones_user_id", "milestones", ["user_id"])

    # ── 10. tasks ─────────────────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("milestone_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="todo"),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("source", sa.Text, nullable=False, server_default="coach"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["milestone_id"], ["milestones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_tasks_user_status", "tasks", ["user_id", "status"])
    op.create_index("ix_tasks_milestone_id", "tasks", ["milestone_id"])

    # ── 11. relationships ─────────────────────────────────────────────────────
    op.create_table(
        "relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("role", sa.Text, nullable=True),
        sa.Column("attributes", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("importance", sa.Integer, nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_relationships_user_id", "relationships", ["user_id"])

    # ── 12. timeline_events ───────────────────────────────────────────────────
    op.create_table(
        "timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=True),
        sa.Column("event_date", sa.Date, nullable=True),
        sa.Column("is_anticipated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_timeline_events_user_id", "timeline_events", ["user_id"])
    op.create_index("ix_timeline_events_date", "timeline_events", ["user_id", "event_date"])

    # ── 13. insights (reflection memory) ──────────────────────────────────────
    op.create_table(
        "insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("importance", sa.Integer, nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["coaching_sessions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_insights_user_id", "insights", ["user_id"])

    # ── 14. semantic_facts (versioned belief store) ────────────────────────────
    op.create_table(
        "semantic_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("predicate", sa.Text, nullable=False),
        sa.Column("value", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("source_ref", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["superseded_by"], ["semantic_facts.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_semantic_facts_user_id", "semantic_facts", ["user_id"])
    op.execute("""
        CREATE INDEX ix_semantic_facts_user_predicate_current
        ON semantic_facts (user_id, predicate)
        WHERE valid_to IS NULL
    """)

    # ── 15. episodic_memories ─────────────────────────────────────────────────
    op.create_table(
        "episodic_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("salience", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("emotion", sa.Text, nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("decay_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["coaching_sessions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_episodic_memories_user_salience", "episodic_memories",
                    ["user_id", "salience"])

    # ── 16. preferences ───────────────────────────────────────────────────────
    op.create_table(
        "preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("communication_style", sa.Text, nullable=True),
        sa.Column("coaching_style", sa.Text, nullable=True),
        sa.Column("motivation_style", sa.Text, nullable=True),
        sa.Column("cadence", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_preferences_user_id", "preferences", ["user_id"])

    # ── 17. embeddings (polymorphic vector index + HNSW) ──────────────────────
    op.create_table(
        "embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_type", sa.Text, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text, nullable=False),  # DDL overridden below
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    # Replace the placeholder text column with a real vector column
    op.execute("ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(1536) USING NULL")
    op.create_index("ix_embeddings_user_owner", "embeddings", ["user_id", "owner_type"])
    op.create_index("ix_embeddings_owner", "embeddings", ["owner_type", "owner_id"])
    # HNSW index for approximate nearest-neighbour search (cosine distance)
    op.execute("""
        CREATE INDEX ix_embeddings_hnsw
        ON embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # ── 18. audit_events (append-only, partitioned by month) ──────────────────
    op.execute("""
        CREATE TABLE audit_events (
            id          uuid NOT NULL DEFAULT gen_random_uuid(),
            user_id     uuid,
            actor       text NOT NULL,
            action      text NOT NULL,
            resource    text,
            ip          inet,
            metadata    jsonb NOT NULL DEFAULT '{}',
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)
    for ym_start, ym_end in [
        ("2026-05-01", "2026-06-01"),
        ("2026-06-01", "2026-07-01"),
        ("2026-07-01", "2026-08-01"),
    ]:
        safe = ym_start.replace("-", "_")
        op.execute(f"""
            CREATE TABLE audit_events_{safe}
            PARTITION OF audit_events
            FOR VALUES FROM ('{ym_start}') TO ('{ym_end}')
        """)
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    # ── 19. Row-Level Security ─────────────────────────────────────────────────
    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY user_isolation ON {table}
            USING (user_id = current_setting('app.user_id', true)::uuid)
        """)

    # Audit table is append-only; no RLS policy — the app role should only INSERT
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC")

    # ── 20. updated_at trigger (keep updated_at fresh automatically) ───────────
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    _timestamped_tables = [
        "users", "life_profiles", "domains", "conversations", "goals",
        "projects", "milestones", "tasks", "relationships", "timeline_events",
        "insights", "semantic_facts", "episodic_memories",
    ]
    for table in _timestamped_tables:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """)


def downgrade() -> None:
    # Drop in reverse dependency order
    _timestamped_tables = [
        "users", "life_profiles", "domains", "conversations", "goals",
        "projects", "milestones", "tasks", "relationships", "timeline_events",
        "insights", "semantic_facts", "episodic_memories",
    ]
    for table in _timestamped_tables:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")

    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    for table in [
        "embeddings", "preferences", "episodic_memories", "semantic_facts",
        "insights", "timeline_events", "relationships",
        "tasks", "milestones", "projects", "goals",
        "coaching_sessions", "conversations", "domains", "life_profiles",
    ]:
        op.drop_table(table)

    op.execute("DROP TABLE IF EXISTS messages CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_events CASCADE")
    op.drop_table("users")
