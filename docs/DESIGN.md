# AI Life Coach — Technical Design Document

> **Status:** Draft v1.0 · **Audience:** Founding engineering team (senior) · **Owner:** CTO
> **Scope:** End-to-end architecture, data model, memory system, AI orchestration, security, mobile strategy, roadmap, and cost model for a production-grade, venture-scale AI Life Coach.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Architecture](#2-product-architecture)
3. [System Architecture](#3-system-architecture)
4. [Database Design](#4-database-design)
5. [Memory Architecture](#5-memory-architecture)
6. [AI Orchestration Design](#6-ai-orchestration-design)
7. [Security Design](#7-security-design)
8. [Mobile Strategy](#8-mobile-strategy)
9. [API Design](#9-api-design)
10. [Coaching Methodology & Safety](#10-coaching-methodology--safety)
11. [Development Roadmap](#11-development-roadmap)
12. [MVP Scope](#12-mvp-scope)
13. [Post-MVP Roadmap](#13-post-mvp-roadmap)
14. [Technical Risks](#14-technical-risks)
15. [Cost Estimates](#15-cost-estimates)
16. [Scaling Strategy](#16-scaling-strategy)
17. [Recommended Final Architecture](#17-recommended-final-architecture)
18. [Repository Structure & Service Boundaries](#18-repository-structure--service-boundaries)

---

## 1. Executive Summary

### 1.1 What we are building

An AI Life Coach that maintains a **structured, evolving model of each user's life** and uses it to deliver continuous, goal-oriented coaching across career, business, education, family, finances, habits, and personal growth. The differentiator versus ChatGPT is **persistent structured memory + a coaching methodology + progress tracking**, not open-ended chat.

### 1.2 The three pillars

1. **The Life Model** — a structured, queryable representation of where the user is, where they want to go, their projects, goals, relationships, obstacles, and life stage. This is the moat.
2. **The Memory System** — a multi-layered memory (episodic, semantic, goal, project, relationship, timeline, reflection, preference) with retrieval, ranking, consolidation, and temporal evolution.
3. **The Coaching Engine** — a model-agnostic orchestration layer that retrieves memory, updates the life model, and produces structured coaching guidance grounded in real coaching frameworks (GROW, OKRs, motivational interviewing, behavioral design) with strict safety guardrails.

### 1.3 Key recommendations (TL;DR)

| Decision | Recommendation | Rationale |
|---|---|---|
| Web frontend | **Next.js (App Router) + TypeScript** | SSR, auth-gated app, mature ecosystem, shares TS with mobile |
| Mobile | **React Native + Expo** | Maximum code/skill reuse with web team; one client language (TS) |
| AI/backend core | **Python + FastAPI** | Best-in-class AI/ML ecosystem; matches the memory/RAG-heavy workload |
| Monorepo | **Turborepo** with shared TS packages + a Python service | Share types, API client, and UI logic across web/mobile |
| Provider abstraction | **LiteLLM** as the LLM gateway + a thin in-house `CoachLLM` façade | Unifies OpenAI/Anthropic/Gemini; routing, fallback, cost tracking |
| Database | **PostgreSQL 16 + pgvector** | Single source of truth; vector + relational + JSONB in one system |
| Cache/queue | **Redis** + **Celery** (or Arq) | Standard, well-understood; async memory consolidation jobs |
| Auth | **Clerk** for MVP velocity → **WorkOS** for enterprise SSO | OAuth (Google/X/Meta) + email out of the box; FastAPI verifies JWTs |
| Cloud | **AWS** (ECS Fargate → EKS at scale) | User preference; managed Postgres (RDS/Aurora), KMS, Secrets Manager |
| Vector store | **pgvector now**, **Qdrant** as an escape hatch at >10M vectors | Avoid premature infra; clean migration path |

### 1.4 Stack option evaluation (A–F)

- **Option A (React + FastAPI + Postgres):** Solid, but plain React (Vite) gives up SSR/routing/DX that Next.js provides for an auth-gated product.
- **Option B (Next.js + FastAPI):** **Recommended for web.** Next.js for the web client and a thin BFF; FastAPI owns the AI/memory core. Clear separation of concerns.
- **Option C (React Native):** **Recommended for mobile**, via Expo. Shares language, types, and the API client with the Next.js web app.
- **Option D (Flutter):** Excellent UI runtime, but Dart fragments the team and duplicates the API/types layer. Rejected for a TS-centric team.
- **Option E (Kotlin Multiplatform):** Shares business logic but not UI; adds a third language. Powerful but premature for a startup at this stage.
- **Option F (Java/Spring):** Mature and scalable, but a poor fit for an AI-heavy, iteration-fast product; Python's AI ecosystem is decisive here.

**Verdict:** **B + C.** Next.js web + Expo React Native mobile + FastAPI Python AI core, in a Turborepo monorepo. One client language (TS), one AI language (Python), minimal rewrites across web/Android/iOS.

---

## 2. Product Architecture

### 2.1 Core user journeys

1. **Signup & onboarding** → adaptive interview → structured Life Profile.
2. **Coaching session** → conversational guidance grounded in memory; produces insights, updates goals/projects, suggests next actions.
3. **Progress tracking** → goals, projects, milestones, tasks, streaks; check-ins.
4. **Proactive nudges (post-MVP)** → scheduled check-ins, milestone reminders, life-change detection.
5. **Reflection & review** → weekly/quarterly reviews summarizing progress and surfacing insights.

### 2.2 The Life Model (conceptual)

The Life Model is the structured backbone the AI maintains and the user can see/edit:

```
LifeProfile
├── LifeStage           (e.g., "early-career, newly married, no kids")
├── Domains[]           (career, business, education, family, finances, health, personal-growth, …)
│   ├── currentState    (where they are)
│   ├── desiredState    (where they want to go: 1y / 5y)
│   ├── obstacles[]
│   ├── strengths[]
│   └── priorities (ranked)
├── Goals[]             (short/long-term, linked to domains)
├── Projects[]          (ongoing initiatives, linked to goals)
│   └── Milestones[] → Tasks[]
├── Relationships[]     (spouse, kids, mentors, co-founders…)
├── Timeline[]          (major life events, past & anticipated)
├── Insights[]          (coaching reflections, lessons learned)
└── Preferences         (communication, coaching, motivation style)
```

### 2.3 Onboarding: adaptive interview engine

- **Not a blank chat.** A guided, branching interview that fills a defined **slot schema** (the Life Profile fields).
- **Hybrid design:** a deterministic **question graph** (domains → slots) governs coverage and ordering; an LLM generates natural phrasing, asks intelligent follow-ups, and decides when a slot is "satisfied."
- **Adaptivity rules (examples):**
  - "Do you have children?" = no → skip parenting depth; mark `family.parenting = n/a`.
  - "Are you building a business?" = yes → branch into entrepreneurship slots (stage, revenue, co-founders, runway).
  - Stress signal detected → prioritize the relevant domain.
- **Output:** a populated `LifeProfile` + seeded `goals`, `projects`, `relationships`, and `semantic_facts`, plus an initial `insight` summarizing the user.
- **Resumable:** onboarding state persists; users can pause/resume; completion is a percentage so coaching can start before 100%.
- **Coverage telemetry:** track which domains are thin so the coach can opportunistically deepen them later.

### 2.4 Product principles

- **Show the model, let the user correct it.** Trust comes from transparency; user edits are high-confidence memory signals.
- **Every session ends with a next action.** Coaching is about movement, not conversation.
- **Progress is first-class.** Goals/projects/milestones are real entities, not buried in chat.
- **Safety is non-negotiable.** Clear boundaries vs therapy/medical/legal/financial advice (see §10).

---

## 3. System Architecture

### 3.1 High-level topology

```
                       ┌────────────────────────────────────────────┐
   Web (Next.js)  ─────┤                                            │
   Mobile (Expo)  ─────┤   API Gateway / Edge (ALB + WAF)           │
                       └───────────────────┬────────────────────────┘
                                           │  HTTPS / JSON, JWT (Clerk)
                          ┌────────────────▼─────────────────┐
                          │   FastAPI App (stateless, N pods) │
                          │  - Auth middleware (JWT verify)   │
                          │  - REST + SSE/WebSocket (stream)  │
                          │  - Coaching orchestrator          │
                          │  - Memory retrieval pipeline      │
                          └───┬───────────┬───────────┬───────┘
                              │           │           │
                  ┌───────────▼──┐  ┌─────▼─────┐ ┌───▼─────────────┐
                  │ PostgreSQL   │  │  Redis    │ │  LiteLLM gateway│
                  │ + pgvector   │  │ cache+    │ │  → OpenAI       │
                  │ (RDS/Aurora) │  │ broker+   │ │  → Anthropic    │
                  └───────┬──────┘  │ rate-lim  │ │  → Gemini       │
                          │         └─────┬─────┘ └─────────────────┘
                          │               │
                  ┌───────▼───────────────▼─────────┐
                  │  Celery workers (async jobs)     │
                  │  - memory extraction             │
                  │  - consolidation / summarization │
                  │  - reflection generation         │
                  │  - scheduled check-ins (Beat)    │
                  │  - embeddings backfill           │
                  └──────────────────────────────────┘
```

### 3.2 Components

| Component | Responsibility | Tech |
|---|---|---|
| **Web client** | Authenticated SPA/SSR app, chat UI, life-model dashboards | Next.js, React, TS, TanStack Query, shadcn/ui |
| **Mobile client** | Native iOS/Android app, same flows | Expo (React Native), TS, shared packages |
| **API service** | REST + streaming, auth, orchestration entrypoint | FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic |
| **Coaching orchestrator** | The 6-step coaching pipeline (§6) | Python module, in-process |
| **Memory service** | Storage + retrieval + ranking (in-process module, extractable to a service later) | Python, pgvector |
| **Worker tier** | Async memory writes, consolidation, scheduled jobs | Celery + Redis (or Arq) |
| **LLM gateway** | Provider routing, fallback, cost/latency tracking | LiteLLM (self-hosted lib or proxy) |
| **Datastore** | Relational + vector + JSONB | PostgreSQL 16 + pgvector |
| **Cache/broker** | Sessions, rate limits, hot memory, queue broker | Redis 7 |
| **Object storage** | Exports, attachments, model snapshots | S3 |
| **Observability** | Tracing, logs, metrics, LLM traces | OpenTelemetry, Grafana/Datadog, Langfuse for LLM traces |

### 3.3 Why a Python AI core + TS clients (not all-TS)

The memory/RAG/consolidation workload is the product's center of gravity. Python has the strongest ecosystem (embeddings, eval, data tooling, LiteLLM, scientific libs) and is where the team will iterate fastest on coaching quality. Clients stay in TS for web/mobile reuse. The cost is a network boundary and two languages — acceptable and conventional. *(If the team were AI-light and TS-heavy, the Vercel AI SDK + a single TS backend would be the alternative; given this product's memory ambitions, Python wins.)*

### 3.4 Request lifecycle (a coaching turn)

1. Client sends user message over **SSE/WebSocket** to `/v1/sessions/{id}/messages`.
2. API verifies JWT (Clerk), loads session, applies rate limits (Redis).
3. **Retrieve:** memory pipeline assembles a context budget (§5.4).
4. **Reason:** orchestrator builds the layered prompt, calls LLM via LiteLLM, streams tokens back.
5. **Act:** tool calls (create/update goal, project, task, insight) execute transactionally.
6. **Persist:** message + assistant turn saved; an async **memory-extraction** job is enqueued.
7. Worker later extracts/dedupes facts, updates the life model, generates embeddings, and may produce a reflection.

---

## 4. Database Design

PostgreSQL is the single source of truth. Structured life-model entities are **first-class relational tables** (rich lifecycle, queries, UI). The "memory" abstraction is a **retrieval layer** over these tables plus an embeddings index — not a single opaque blob store.

### 4.1 Entity overview

```
users ──1:1── life_profiles ──1:N── domains
  │
  ├─1:N─ conversations ─1:N─ messages
  ├─1:N─ coaching_sessions
  ├─1:N─ goals ─1:N─ projects ─1:N─ milestones ─1:N─ tasks
  ├─1:N─ relationships
  ├─1:N─ timeline_events
  ├─1:N─ insights (reflection memory)
  ├─1:N─ semantic_facts (versioned facts)
  ├─1:N─ episodic_memories (salient summaries)
  ├─1:N─ preferences
  └─1:N─ audit_events

embeddings ──polymorphic──> (any retrievable unit)
```

### 4.2 Conventions

- **PKs:** `uuid` (v7, time-sortable) for all tables.
- **Tenancy:** every user-owned row carries `user_id`; **Row-Level Security (RLS)** enforces isolation at the DB layer.
- **Timestamps:** `created_at`, `updated_at` (UTC, `timestamptz`), trigger-maintained.
- **Soft delete:** `deleted_at` on user-content tables (hard-delete pipeline for GDPR, §7.6).
- **JSONB** for flexible/semi-structured fields, with `GIN` indexes where queried.
- **Temporal facts:** `valid_from` / `valid_to` for belief revision (§5.5).

### 4.3 Core tables (abridged DDL)

```sql
-- USERS --------------------------------------------------------------
CREATE TABLE users (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  external_auth_id text UNIQUE NOT NULL,        -- Clerk user id
  email           citext UNIQUE NOT NULL,
  email_verified  boolean NOT NULL DEFAULT false,
  display_name    text,
  locale          text DEFAULT 'en',
  timezone        text DEFAULT 'UTC',
  status          text NOT NULL DEFAULT 'active', -- active|suspended|deleting
  onboarding_state text NOT NULL DEFAULT 'pending',
  consent         jsonb NOT NULL DEFAULT '{}',   -- gdpr consents, versions
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz
);

-- LIFE PROFILE -------------------------------------------------------
CREATE TABLE life_profiles (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  life_stage  text,                              -- derived label
  summary     text,                              -- rolling natural-language summary
  attributes  jsonb NOT NULL DEFAULT '{}',       -- age_range, marital_status, dependents…
  completeness numeric(4,3) DEFAULT 0,           -- onboarding coverage 0..1
  version     int NOT NULL DEFAULT 1,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE domains (                           -- career, family, finances…
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        text NOT NULL,                     -- enum-ish: career|business|education|…
  current_state text,
  desired_1y  text,
  desired_5y  text,
  obstacles   jsonb DEFAULT '[]',
  strengths   jsonb DEFAULT '[]',
  priority    int DEFAULT 0,                      -- ranked
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, kind)
);

-- CONVERSATIONS & MESSAGES ------------------------------------------
CREATE TABLE conversations (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title       text,
  kind        text NOT NULL DEFAULT 'coaching',  -- coaching|onboarding|review
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE messages (                          -- PARTITIONED (see §4.5)
  id            uuid DEFAULT uuidv7(),
  conversation_id uuid NOT NULL,
  user_id       uuid NOT NULL,
  role          text NOT NULL,                   -- user|assistant|system|tool
  content       text NOT NULL,
  tokens        int,
  model         text,
  tool_calls    jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (created_at, id)
) PARTITION BY RANGE (created_at);

-- COACHING SESSIONS --------------------------------------------------
CREATE TABLE coaching_sessions (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  conversation_id uuid REFERENCES conversations(id) ON DELETE SET NULL,
  focus_domain  text,
  summary       text,
  detected_changes jsonb DEFAULT '[]',           -- life-change signals
  outcome_actions jsonb DEFAULT '[]',
  sentiment     jsonb,                            -- coarse affect signals
  started_at    timestamptz NOT NULL DEFAULT now(),
  ended_at      timestamptz
);

-- GOALS / PROJECTS / MILESTONES / TASKS ------------------------------
CREATE TABLE goals (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  domain_id   uuid REFERENCES domains(id) ON DELETE SET NULL,
  title       text NOT NULL,
  description text,
  horizon     text NOT NULL,                      -- short|long
  target_date date,
  status      text NOT NULL DEFAULT 'active',     -- active|achieved|paused|dropped
  progress    numeric(4,3) DEFAULT 0,
  importance  int DEFAULT 3,                       -- 1..5 user/AI priority
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE projects (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  goal_id     uuid REFERENCES goals(id) ON DELETE SET NULL,
  title       text NOT NULL,
  kind        text,                                -- startup|side-business|certification|fitness…
  status      text NOT NULL DEFAULT 'active',
  health      text,                                -- on_track|at_risk|stalled
  metadata    jsonb DEFAULT '{}',                  -- revenue, runway, etc.
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE milestones (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title       text NOT NULL,
  due_date    date,
  status      text NOT NULL DEFAULT 'pending',
  achieved_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tasks (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  milestone_id uuid REFERENCES milestones(id) ON DELETE CASCADE,
  goal_id     uuid REFERENCES goals(id) ON DELETE SET NULL,
  title       text NOT NULL,
  status      text NOT NULL DEFAULT 'todo',        -- todo|doing|done|dropped
  due_date    date,
  source      text DEFAULT 'coach',                -- coach|user
  created_at  timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

-- RELATIONSHIPS / TIMELINE / INSIGHTS --------------------------------
CREATE TABLE relationships (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name        text,
  role        text,                                -- spouse|child|mentor|cofounder…
  attributes  jsonb DEFAULT '{}',                  -- age, notes, importance
  importance  int DEFAULT 3,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE timeline_events (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title       text NOT NULL,
  kind        text,                                -- graduation|marriage|job-change|birth…
  event_date  date,
  is_anticipated boolean DEFAULT false,
  metadata    jsonb DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE insights (                            -- reflection memory
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id  uuid REFERENCES coaching_sessions(id) ON DELETE SET NULL,
  kind        text NOT NULL,                        -- lesson|pattern|coaching-note
  content     text NOT NULL,
  importance  int DEFAULT 3,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- SEMANTIC FACTS (versioned) -----------------------------------------
CREATE TABLE semantic_facts (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  predicate   text NOT NULL,                        -- 'occupation','spouse_name','age_range'…
  value       jsonb NOT NULL,
  confidence  numeric(4,3) NOT NULL DEFAULT 0.7,
  source      text NOT NULL,                         -- onboarding|message|user-edit|inference
  source_ref  uuid,                                  -- message/session provenance
  valid_from  timestamptz NOT NULL DEFAULT now(),
  valid_to    timestamptz,                           -- NULL = currently believed
  superseded_by uuid REFERENCES semantic_facts(id),
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- EPISODIC MEMORY (salient summaries) --------------------------------
CREATE TABLE episodic_memories (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id  uuid REFERENCES coaching_sessions(id) ON DELETE SET NULL,
  summary     text NOT NULL,
  salience    numeric(4,3) NOT NULL DEFAULT 0.5,     -- importance score
  emotion     text,
  last_accessed_at timestamptz,
  access_count int DEFAULT 0,
  decay_score numeric(4,3),                           -- computed, for pruning
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- PREFERENCES --------------------------------------------------------
CREATE TABLE preferences (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  communication_style text,                           -- direct|warm|socratic…
  coaching_style text,                                -- challenger|supporter|accountability…
  motivation_style text,                              -- intrinsic|achievement|fear-avoidant…
  cadence     jsonb DEFAULT '{}',                     -- check-in frequency prefs
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- EMBEDDINGS (polymorphic vector index) ------------------------------
CREATE TABLE embeddings (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  owner_type  text NOT NULL,    -- 'episodic'|'semantic'|'insight'|'goal'|'project'|'message'
  owner_id    uuid NOT NULL,
  model       text NOT NULL,    -- embedding model id (for re-embed migrations)
  content     text NOT NULL,    -- the embedded text (for re-rank/debug)
  embedding   vector(1536) NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- AUDIT (append-only) ------------------------------------------------
CREATE TABLE audit_events (                          -- PARTITIONED by month
  id          uuid DEFAULT uuidv7(),
  user_id     uuid,
  actor       text NOT NULL,    -- user id, 'system', 'coach'
  action      text NOT NULL,    -- auth.login, memory.write, data.export, account.delete…
  resource    text,
  ip          inet,
  metadata    jsonb DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (created_at, id)
) PARTITION BY RANGE (created_at);
```

### 4.4 Indexes

```sql
-- Hot lookups
CREATE INDEX ON conversations (user_id, updated_at DESC);
CREATE INDEX ON messages (conversation_id, created_at);
CREATE INDEX ON goals (user_id, status, importance DESC);
CREATE INDEX ON projects (user_id, status);
CREATE INDEX ON semantic_facts (user_id, predicate) WHERE valid_to IS NULL;
CREATE INDEX ON episodic_memories (user_id, salience DESC);

-- JSONB
CREATE INDEX ON domains USING gin (obstacles);
CREATE INDEX ON life_profiles USING gin (attributes);

-- Vector (HNSW for recall+latency; per-user filtering via WHERE user_id=)
CREATE INDEX ON embeddings USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
CREATE INDEX ON embeddings (user_id, owner_type);
```

### 4.5 Partitioning strategy

- **`messages`** and **`audit_events`**: **range-partition by month** (`created_at`). Old partitions are cheap to archive to S3/Glacier and detach. Keeps hot indexes small.
- **`embeddings`**: start single-table with HNSW; if it grows, **partition by `user_id` hash** or migrate to Qdrant (§16). Always filter vector search by `user_id` to keep per-user recall fast and isolated.
- Use **`pg_partman`** to automate partition creation/retention.

### 4.6 Audit logging & RLS

- **RLS:** `CREATE POLICY user_isolation ON <table> USING (user_id = current_setting('app.user_id')::uuid)`. The API sets `app.user_id` per request/transaction. Defense-in-depth against query bugs.
- **Audit:** append-only `audit_events`, write-path enforced in the service layer; optionally `pgaudit` for DB-level DDL/DML auditing. Audit is immutable (no UPDATE/DELETE grants for app role).

---

## 5. Memory Architecture

This is the core IP. The design goal: the coach should feel like it *remembers and understands* the user over months, while staying token-efficient and accurate.

### 5.1 Memory taxonomy → storage mapping

| Memory type | Primary store | Vectorized? | Lifecycle |
|---|---|---|---|
| **Episodic** (salient conversations) | `episodic_memories` | Yes | summarized → decays/prunes |
| **Semantic** (facts) | `semantic_facts` (versioned) | Yes (the fact text) | belief revision, supersession |
| **Goal** | `goals` | Yes (title+desc) | status lifecycle |
| **Project** | `projects` + `milestones`/`tasks` | Yes | health tracking |
| **Relationship** | `relationships` | Yes | updated as life changes |
| **Timeline** | `timeline_events` | Optional | append-mostly |
| **Reflection** | `insights` | Yes | accumulates, periodically distilled |
| **Preference** | `preferences` | No (always loaded) | slowly evolving |

**Key principle:** structured entities live in typed tables (queryable, editable, UI-friendly); the **`embeddings` table is a unified semantic index** pointing at any of them. Retrieval blends structured queries with vector search.

### 5.2 Writing memory (extraction pipeline)

After each coaching turn/session, an async Celery job runs:

1. **Extract candidates** — an LLM with a strict JSON schema proposes: new/changed facts, new goals/projects/tasks, relationship updates, timeline events, insights, detected life changes.
2. **Resolve & dedupe** — for each candidate, vector-search existing memories of the same type for the user. If a near-duplicate exists, **update** (raise confidence / refresh `last_accessed`) instead of inserting.
3. **Belief revision** — if a new fact contradicts a current one (same `predicate`), close the old (`valid_to = now`, `superseded_by`) and insert the new with provenance. Contradictions are logged for the coach to optionally confirm with the user.
4. **Score salience/importance** — heuristic + LLM signal (emotional weight, goal-relevance, novelty).
5. **Embed** — generate embeddings for new/changed units, write to `embeddings`.
6. **Update the rolling profile summary** — keep `life_profiles.summary` current (cheap, high-leverage context).

Extraction is **idempotent** (keyed on session/message) so retries don't duplicate.

### 5.3 Memory ranking model

Each retrievable unit gets a composite **retrieval score**:

```
score = w_sim · cosine_similarity(query, unit)
      + w_imp · importance_norm           (user/AI-assigned 1..5)
      + w_rec · recency_decay             (exp(-Δt / τ_type))
      + w_acc · access_frequency_norm     (often-used memories surface)
      + w_type· type_priority(query_intent)   (e.g., goal-talk boosts goals)
      − w_red · redundancy_penalty        (MMR-style diversity)
```

- **Per-type half-life `τ_type`:** preferences/semantic facts decay slowly; episodic decays faster; goals/projects don't decay while `active`.
- **Weights** are configurable and **tuned via the eval harness** (§6.6), not guessed forever.
- **MMR** ensures the assembled context isn't five paraphrases of the same fact.

### 5.4 Retrieval pipeline (per coaching turn)

```
1. Classify intent of the incoming message (domain, is it goal/project/reflection talk?).
2. ALWAYS-LOAD core context (cheap, structured):
   - life_profiles.summary, preferences, active goals (top N by importance),
     active projects + health, recent timeline events.
3. SEMANTIC RECALL (vector): embed the query + recent window;
   ANN search over embeddings WHERE user_id = …, top-K per owner_type.
4. STRUCTURED RECALL: SQL pulls (e.g., tasks due soon, stalled projects).
5. RANK & FUSE: apply the §5.3 scoring; MMR de-dup.
6. BUDGET ASSEMBLER: fit into a token budget (e.g., 2–4k tokens of memory),
   prioritizing always-load > high-score recall. Truncate/summarize overflow.
7. Emit a structured "context block" for the prompt (§6.4).
```

Hybrid (vector + structured + always-load) avoids the classic RAG failure of "the obvious fact wasn't retrieved." Core identity facts are *always* present.

### 5.5 Memory evolution & temporal model

- **Versioned facts** (`valid_from`/`valid_to`/`superseded_by`) give the coach a *history* ("you used to be at Company X; now you're founding a startup") and prevent stale beliefs.
- **Confidence** rises with repetition/user confirmation, falls with contradiction/age. Low-confidence facts are hedged in prompts ("I think you mentioned…").
- **Provenance** (`source`, `source_ref`) lets us show the user *why* the coach believes something and supports correction.

### 5.6 Consolidation & summarization (the "sleep" jobs)

Scheduled (Celery Beat) background jobs that keep memory compact and insightful:

- **Episodic consolidation:** cluster recent episodic memories; distill clusters into durable semantic facts/insights; lower salience of the raw episodes.
- **Decay & prune:** recompute `decay_score`; archive/prune low-salience, low-access episodic memories beyond a horizon (never auto-delete structured goals/relationships).
- **Reflection generation:** weekly/quarterly, generate higher-order insights ("pattern: you start projects when stressed and abandon them in week 3") and a progress review.
- **Profile re-summarization:** regenerate `life_profiles.summary` from current structured state.
- **Embedding migration:** when we change embedding models, re-embed in the background (versioned by `embeddings.model`).

### 5.7 Memory privacy & control

- Users can **view, edit, and delete** any memory (it's their life model). Edits are high-confidence signals.
- Sensitive predicates (health, finances) can be flagged for **column-level encryption** (§7.1) and excluded from provider context unless needed.
- Hard-delete cascades through `embeddings` (GDPR, §7.6).

---

## 6. AI Orchestration Design

### 6.1 Provider abstraction

- **LiteLLM** is the gateway: one interface to OpenAI, Anthropic, and Gemini, with normalized chat/complet, streaming, tool-calling, and embeddings; built-in retries, fallbacks, and cost/latency logging.
- A thin in-house **`CoachLLM` façade** wraps LiteLLM to: enforce our prompt contracts, attach safety classifiers, redact PII before egress, and emit traces to **Langfuse**.
- **Model router policy** (per task, configurable):

| Task | Default | Why |
|---|---|---|
| Coaching response (quality-critical) | Claude (Opus/Sonnet) or GPT-class | Best reasoning + tone |
| Memory extraction (structured JSON) | A cheaper fast model (Haiku/GPT-mini/Gemini Flash) | Volume, schema-bound |
| Onboarding follow-ups | Mid-tier | Latency-sensitive, conversational |
| Embeddings | One provider's embedding model, pinned | Consistency of vector space |
| Eval judge | A different family than the generator | Reduce self-preference bias |

Fallback chains (e.g., Anthropic → OpenAI → Gemini) handle provider outages. **Model choice is config, not code** — the coaching engine is model-agnostic.

### 6.2 Agent architecture: structured pipeline, not free-roaming agent

For reliability and cost control, the coaching engine is a **deterministic pipeline with tool-calling**, not an autonomous multi-agent loop. The orchestrator runs the **six required steps**:

```
1. RETRIEVE   → memory pipeline (§5.4) assembles context.
2. UNDERSTAND → intent + state classifier (domain, sentiment, change signals,
                safety screen) over the message + context.
3. UPDATE     → tool calls to mutate the life model (create/adjust goal,
                project, task, relationship, timeline event). Transactional.
4. GUIDE      → generate the coaching response (grounded in §10 methodology,
                styled by preferences, constrained by safety guardrails).
5. ASK        → generate adaptive follow-up question(s) to advance the goal.
6. DETECT     → emit life-change/progress signals → feed memory + nudges.
```

Steps 2/6 (classification) and 4/5 (generation) can be merged into fewer LLM calls for latency, using structured output. Heavy work (full extraction/consolidation) is deferred to async workers (§5.2/5.6) so the live turn stays fast.

### 6.3 Tools (function-calling surface)

`create_goal`, `update_goal_progress`, `create_project`, `update_project_health`, `create_milestone`, `create_task`, `complete_task`, `upsert_relationship`, `add_timeline_event`, `record_insight`, `flag_safety_concern`, `request_user_confirmation` (for low-confidence belief changes). Tools are validated server-side (Pydantic) and executed transactionally with audit entries.

### 6.4 Prompt architecture (layered)

```
┌ System layer (static, cached) ──────────────────────────────┐
│  • Coach persona & voice                                     │
│  • Coaching methodology (GROW/OKR/MI/behavioral design)      │
│  • Hard safety guardrails (no therapy/medical/legal/finance) │
│  • Output contract (response + tool calls + follow-ups)      │
├ Profile layer (per-user, semi-static) ──────────────────────┤
│  • life_profiles.summary, life_stage, preferences            │
├ Memory context layer (per-turn, dynamic) ───────────────────┤
│  • Assembled, ranked memory block from §5.4 (token-budgeted) │
│  • Active goals/projects/tasks, recent timeline, open loops  │
├ Conversation layer ─────────────────────────────────────────┤
│  • Recent message window (rolling; older turns summarized)   │
└ User turn ──────────────────────────────────────────────────┘
```

The **system + profile layers are prompt-cached** (Anthropic prompt caching / provider equivalents) to cut cost and latency, since they change rarely within a session.

### 6.5 RAG strategy

- **Hybrid retrieval** (vector + structured + always-load), per §5.4 — not naive top-k over raw chat history.
- **Query expansion:** embed the user turn *plus* a short rolling intent summary, so retrieval reflects the thread, not just the last sentence.
- **Re-ranking:** composite score (§5.3) + MMR; optionally a cross-encoder re-ranker at scale.
- **Grounding & provenance:** memory units carry IDs so the coach can reference and the UI can link ("Based on your goal *Launch MVP by Sept*…").
- **Anti-hallucination:** low-confidence facts are hedged; the model is instructed to ask rather than invent when memory is thin.

### 6.6 Evaluation framework

A first-class concern — coaching quality and safety must be measurable.

- **Offline eval sets:** curated synthetic + (consented) real scenarios with rubrics. **LLM-as-judge** (different model family) scores: relevance, actionability, methodology adherence, tone match, safety.
- **Memory eval:** precision/recall of fact extraction; retrieval hit-rate ("was the needed fact present?"); contradiction-handling tests.
- **Safety regression suite:** red-team prompts (self-harm, medical/legal/financial bait, prompt injection); must pass before deploy. **CI gate.**
- **Online metrics:** session completion, action-acceptance rate, goal progress over time, retention/streaks, thumbs up/down, escalation rate.
- **Tracing:** every LLM call traced in **Langfuse** (inputs, retrieved memory, cost, latency, scores) for debugging and dataset curation.
- **Experimentation:** prompt/model/weight changes are flagged and A/B tested; eval scores gate promotion.

---

## 7. Security Design

### 7.1 Encryption

- **In transit:** TLS 1.2+ everywhere; HSTS; internal service mTLS at scale.
- **At rest:** RDS/Aurora encryption (KMS), encrypted S3, encrypted EBS.
- **Field-level:** sensitive memory predicates (health, finances, relationship details) encrypted at the application layer with **AWS KMS envelope encryption** (per-user data keys), so a DB dump alone doesn't expose them.

### 7.2 Secrets management

- **AWS Secrets Manager** (+ rotation) for DB creds, provider API keys, OAuth secrets. No secrets in env files in prod; injected at runtime. Local dev uses `.env` (gitignored) with non-prod keys.

### 7.3 Authentication

- **Clerk** for MVP: Google, X/Twitter, Meta/Facebook OAuth + email/password, MFA, session management, bot protection. FastAPI verifies Clerk **JWTs** (JWKS) on every request; `users.external_auth_id` links Clerk → our user.
- **Enterprise path:** **WorkOS** (SAML/OIDC SSO, SCIM) when B2B arrives — swap/extend the auth provider behind the same JWT-verification seam.
- **No-vendor fallback:** FastAPI-Users + Authlib if we ever need to self-host. The JWT-verification boundary keeps this swappable.

### 7.4 Authorization

- **RLS** at the DB (per-user isolation) + **service-layer checks** (resource ownership). Role model: `user`, `admin`, `support` (scoped, audited), future `org_admin` for enterprise.

### 7.5 Rate limiting & abuse prevention

- **Redis token-bucket** rate limits per user/IP/endpoint; stricter on LLM-cost endpoints. Per-user **monthly LLM budget caps** with graceful degradation (cheaper model / queueing).
- **Abuse:** WAF (AWS WAF / Vercel BotID on the edge), anomaly detection on spend, CAPTCHA on auth where needed, content filtering on inputs.

### 7.6 Privacy, GDPR, deletion & export

- **Consent tracking** (`users.consent`, versioned) for ToS/privacy/AI-processing.
- **Data export:** async job assembles a full **JSON + Markdown** archive (profile, memories, goals, conversations) to a signed S3 URL.
- **Account deletion:** soft-delete → `status=deleting` → async **hard-delete pipeline** purges all user rows incl. `embeddings`, cancels provider data (we use **zero-retention provider settings** so prompts aren't retained), and emits an immutable audit record. Target SLA: complete within 30 days (GDPR), typically hours.
- **Data minimization to providers:** redact direct identifiers (names → tokens where feasible) before LLM egress; prefer providers/configs with **no training on our data** and zero retention.
- **DPA & region:** data resident in chosen AWS region; DPAs with LLM providers; PII inventory maintained.

### 7.7 AI safety (engineering)

- **Prompt-injection defense:** treat retrieved memory/user content as untrusted; the system layer is privileged and instructs the model to ignore embedded instructions in user data; tool calls validated server-side.
- **Output moderation:** safety classifier on inputs and outputs; crisis/medical/legal/financial detection routes to the escalation flow (§10).
- **Guardrail tests** gate CI (§6.6).

---

## 8. Mobile Strategy

### 8.1 Goal: Web + Android + iOS with minimal rewrites

**Recommended path: a Turborepo monorepo with shared TypeScript packages, a Next.js web app, and an Expo (React Native) mobile app, both consuming the same FastAPI backend.**

```
packages/
  types/        ← shared domain types + zod schemas (single source for client)
  api-client/   ← typed client (generated from OpenAPI), auth, SSE/streaming
  core/         ← framework-agnostic logic (state machines, formatting, validation)
  ui/           ← shared design tokens; primitives where RN/web overlap
apps/
  web/          ← Next.js (App Router)
  mobile/       ← Expo (React Native) — iOS + Android from one codebase
```

- **What's shared:** all domain types, the API client, auth flow, business/validation logic, analytics — typically the majority of non-view code.
- **What's not:** view layer (RN components vs. DOM). React Native for Web can share more, but we keep web on Next.js for SSR/SEO/performance.
- **Streaming:** SSE works in both; RN needs a compatible fetch/EventSource polyfill (or WebSocket) — abstracted in `api-client`.
- **Auth:** Clerk has both React and Expo SDKs → one mental model across platforms.
- **Push & background:** Expo Notifications for proactive nudges; native modules via Expo config plugins as needed.

### 8.2 Why not Flutter / KMP

- **Flutter:** best-in-class UI, but Dart forks the team and duplicates the types/API/logic layer that RN shares with web. For a TS team optimizing velocity, the integration tax outweighs the UI polish.
- **Kotlin Multiplatform:** shares logic but not UI, and adds a third language — premature now. Revisit only if we hit RN performance ceilings on a specific surface.

**Verdict:** **Next.js + Expo (React Native)** is the minimal-rewrite path to all three platforms for this team.

---

## 9. API Design

### 9.1 Conventions

- **REST + JSON**, versioned under `/v1`. **OpenAPI** auto-generated by FastAPI → drives the TS `api-client` (typed end-to-end).
- **Streaming** coaching responses via **SSE** (`text/event-stream`).
- **Auth:** `Authorization: Bearer <Clerk JWT>`; idempotency keys on mutating LLM endpoints; cursor pagination; RFC-9457 problem+json errors.

### 9.2 Core endpoints (representative)

```
# Auth/session (mostly Clerk-managed; backend verifies + provisions)
POST   /v1/auth/sync                 → upsert user from verified JWT

# Onboarding
GET    /v1/onboarding                → current state + next question(s)
POST   /v1/onboarding/answer         → submit answer, get adaptive follow-up
POST   /v1/onboarding/complete       → finalize → Life Profile

# Life model
GET    /v1/profile                   → life profile + domains + summary
PATCH  /v1/profile                   → user edits (high-confidence memory)
GET    /v1/goals  POST /v1/goals  PATCH /v1/goals/{id}
GET    /v1/projects … /milestones … /tasks …    (CRUD)
GET    /v1/relationships  /timeline  /insights  (CRUD where applicable)

# Coaching
POST   /v1/conversations             → start conversation
POST   /v1/sessions/{id}/messages    → send message (SSE stream of response)
GET    /v1/sessions/{id}             → session summary, detected changes, actions

# Memory
GET    /v1/memory                    → browse/search user's memories
PATCH  /v1/memory/{id}               → correct a fact (provenance preserved)
DELETE /v1/memory/{id}               → forget

# Reviews / progress
GET    /v1/reviews/weekly            → generated progress review

# Privacy
POST   /v1/account/export            → enqueue export job → signed URL
DELETE /v1/account                   → enqueue deletion pipeline
```

### 9.3 Streaming contract (SSE events)

`token` (partial text) · `tool_call` (life-model mutation) · `followups` (suggested questions) · `change_detected` (life-change signal) · `safety` (escalation) · `done` (final session delta).

---

## 10. Coaching Methodology & Safety

### 10.1 Methodology foundation

The coach blends established frameworks (encoded in the system prompt and pipeline):

- **GROW** (Goal, Reality, Options, Will) — session structure.
- **OKRs + SMART goals** — goal/project definition and progress.
- **Motivational Interviewing** — eliciting the user's own motivation; non-directive where appropriate.
- **Behavioral design / Atomic Habits / Tiny Habits** — habit formation, cue-routine-reward, implementation intentions.
- **Immunity to Change (Kegan)** — surfacing competing commitments behind stuck goals.
- **Executive/career coaching patterns** — accountability, reframing, options generation.

The coach **adapts style** to `preferences` (challenger vs. supporter; direct vs. socratic; intrinsic vs. achievement motivation).

### 10.2 What the coach must NOT do

It is **not** a therapist, doctor, lawyer, or financial advisor. It must not diagnose, prescribe, give medical/legal advice, or give specific financial/investment advice. It maintains a **coaching** frame: goals, behavior, planning, accountability, reflection.

### 10.3 Safety & escalation system

- **Crisis detection** (self-harm, abuse, acute mental-health risk): the safety classifier (§6.6/7.7) triggers a **non-coaching response**: empathetic acknowledgment, encouragement to seek professional help, and **localized crisis-resource hotlines** (geo-aware). Stop coaching; never attempt therapy. Flag `flag_safety_concern`, audit, and surface to support tooling (no automated provider lock-out, but reviewable).
- **Domain redirection** (medical/legal/financial): provide a brief disclaimer, keep it general/educational, and **recommend a licensed professional**; pivot back to coachable behavior ("I can't advise on the investment itself, but we can plan how you'll get qualified advice and decide by Friday").
- **Disclaimers:** clear at onboarding and contextually when boundaries are approached.
- **Human-in-the-loop (post-MVP):** flagged sessions reviewable by trained reviewers / partnership with professional referral networks.

---

## 11. Development Roadmap

| Phase | Duration (est.) | Theme | Exit criteria |
|---|---|---|---|
| **P0 — Foundations** | 3–4 wks | Monorepo, CI/CD, auth, DB schema, LLM gateway, tracing, eval skeleton | A logged-in user can hit a trivial streamed coach reply; eval + safety CI gates exist |
| **P1 — MVP** | 6–8 wks | Onboarding → Life Profile, coaching loop, core memory (semantic+episodic+goals+projects), web app, privacy basics | A user onboards, gets grounded coaching that remembers them across sessions, tracks goals; export/delete work |
| **P2 — Depth & Mobile** | 6–8 wks | Consolidation/reflection jobs, full memory ranking + evolution, Expo mobile app, reviews, richer life-model UI | Memory feels durable & smart; iOS/Android beta in stores; weekly reviews shipped |
| **P3 — Proactive & Scale** | 8–10 wks | Proactive nudges/check-ins, life-change detection actions, A/B experimentation, performance/scale hardening | Retention-driving proactive features; SLOs met under load |
| **P4 — Enterprise & Ecosystem** | ongoing | WorkOS SSO/SCIM, integrations (calendar), team/coach-collab, advanced analytics | First B2B/SSO customer; integration marketplace |

---

## 12. MVP Scope

**In:**
- Auth (Google/X/Meta/email via Clerk), account provisioning.
- **Adaptive onboarding** → structured Life Profile (semantic facts, domains, seed goals/projects/relationships).
- **Coaching loop:** streamed responses, the 6-step pipeline (lightweight), tool calls to create/update goals/projects/tasks/insights.
- **Memory v1:** semantic facts (versioned), episodic summaries, goals/projects/tasks, hybrid retrieval (vector + always-load), async extraction job, rolling profile summary.
- **Life-model dashboard** (web): view/edit profile, goals, projects.
- **Safety v1:** crisis + domain-boundary classifiers and escalation.
- **Privacy v1:** export + account deletion pipeline; audit log.
- **Web only** (Next.js). Observability + eval/safety CI gates.

**Out (deferred):**
- Mobile apps, consolidation/reflection jobs, proactive nudges, advanced ranking tuning, enterprise SSO, integrations, A/B platform.

**MVP success metrics:** onboarding completion rate, week-1 and week-4 retention, sessions/user/week, action-acceptance rate, "the coach remembers me" qualitative signal, zero safety-gate regressions.

---

## 13. Post-MVP Roadmap

- **Memory maturity:** consolidation, decay/prune, reflection generation, cross-session pattern detection, confidence/belief-revision UX ("Is this still true?").
- **Proactive coaching:** scheduled check-ins, milestone/streak nudges, life-change-triggered outreach (Celery Beat + push).
- **Mobile:** Expo iOS/Android GA with push notifications.
- **Reviews:** weekly/quarterly progress reviews and planning sessions.
- **Personalization:** learned coaching/motivation style; tone adaptation.
- **Integrations:** calendar (time-blocking tasks), optional health/finance read-only context (privacy-gated).
- **Enterprise:** WorkOS SSO/SCIM, org accounts, human-coach collaboration mode.
- **Quality flywheel:** continuous eval datasets from real (consented) sessions; model/prompt experimentation.

---

## 14. Technical Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **Memory hallucination / wrong beliefs** | Erodes trust (core value) | Hybrid retrieval w/ always-load, confidence + provenance, hedging low-confidence, user-editable model, contradiction handling, retrieval-recall eval |
| **LLM cost blowup** | Margin/runway | Prompt caching, cheap models for extraction, per-user budget caps, batching async work, token-budgeted context |
| **Provider outage / rate limits** | Downtime | LiteLLM fallback chains across 3 providers; queue + retry; degrade gracefully |
| **Safety failure (therapy/crisis mishandled)** | Severe (harm + liability) | Safety classifiers, escalation flow, CI red-team gate, disclaimers, human review for flags |
| **Privacy/regulatory (GDPR, sensitive data)** | Legal | Field-level encryption, zero-retention provider config, export/delete, DPAs, data minimization, audit |
| **Prompt injection via memory/user content** | Data exfil / misbehavior | Treat memory as untrusted, privileged system layer, server-side tool validation |
| **Vector search scale (latency/recall)** | UX degradation | Per-user filtered HNSW; partition or migrate to Qdrant at >10M vectors |
| **Coaching quality is subjective/hard to measure** | Product-market fit | Rubric-based LLM-judge eval + online behavioral metrics + tight feedback loop |
| **Two-language complexity (TS+Python)** | Velocity drag | OpenAPI-generated client, shared schemas, strong CI, clear service boundary |
| **Scope creep on "life model"** | Slow MVP | Slot-schema discipline; ship narrow, deepen later |

---

## 15. Cost Estimates

Order-of-magnitude, to be refined with load tests. Assumes prompt caching, cheap models for extraction, and ~2–4k tokens of assembled memory per turn.

**Per active user / month (LLM):**
- Coaching: assume ~40 turns/mo × (~3k in cached + ~1.5k fresh + ~600 out). With caching + mid-tier models ≈ **$0.30–$1.20/user/mo**.
- Memory extraction (cheap model, async, ~1 call/turn): **$0.05–$0.20**.
- Embeddings: negligible (**< $0.02**).
- **Heavy-usage power users** can hit several dollars — hence per-user budget caps and tiered pricing.

**Infra (early, AWS):**
- ECS Fargate (API + workers): **~$150–$500/mo** at low scale.
- RDS/Aurora Postgres (with pgvector): **~$150–$600/mo** (start small, scale up).
- Redis (ElastiCache): **~$50–$150/mo**.
- S3 + data transfer + WAF + KMS + Secrets: **~$50–$150/mo**.
- Observability (Langfuse self-host or cloud, Datadog/Grafana): **~$50–$300/mo**.
- **Early total infra ≈ $500–$1,700/mo**, dominated by Postgres and observability.

**Managed services:** Clerk (free→~$25+/mo by MAU tiers), later WorkOS (per-SSO-connection pricing).

**Takeaway:** at small scale, **infra ≈ fixed several hundred/mo**, and **LLM cost scales ~linearly with engaged users (~$0.5–$1.5 each)**. Pricing should ensure ARPU comfortably exceeds blended per-user LLM cost (target ≥ 5–10× at typical usage).

---

## 16. Scaling Strategy

- **Stateless API** → horizontal scale behind ALB; HPA on CPU/concurrency. Sessions/state in Redis/Postgres, not pods.
- **Async-first:** push extraction/consolidation/reflection to Celery workers; scale worker pool independently; use queue priorities (live-adjacent vs. nightly).
- **Postgres:** vertical first; **read replicas** for read-heavy memory/profile loads; **partitioning** for `messages`/`audit_events`; PgBouncer connection pooling; move cold partitions to S3.
- **Vector:** pgvector + HNSW with per-user filters scales to millions; beyond ~10M vectors or strict latency SLAs, migrate `embeddings` to **Qdrant** (clean seam — embeddings already abstracted and re-embeddable).
- **LLM:** provider fallback + regional capacity; batch and cache; consider provider-side batch APIs for nightly jobs; per-user budgets protect spend.
- **Caching:** Redis for hot profile/memory blocks, prompt-cache at the provider, CDN for web assets.
- **Multi-region (later):** start single-region; add read replicas/region for latency and data residency as enterprise demands.
- **Observability-driven:** SLOs on coaching-turn latency (p95 streamed first-token < ~1.5s, full < ~6s), retrieval latency, worker backlog, LLM error/fallback rate, cost/user.

---

## 17. Recommended Final Architecture

**Clients:** Next.js (web) + Expo React Native (iOS/Android), TypeScript, in a **Turborepo** monorepo with shared `types`/`api-client`/`core` packages.

**Backend:** Python **FastAPI** AI core (stateless), **Celery + Redis** workers for async memory/consolidation/nudges, **LiteLLM** gateway over **OpenAI + Anthropic + Gemini** with routing/fallback, **Langfuse** for LLM tracing, eval + safety **CI gates**.

**Data:** **PostgreSQL 16 + pgvector** as single source of truth — first-class life-model tables + a unified polymorphic **embeddings** index + versioned **semantic_facts** for belief revision; RLS for isolation; partitioned `messages`/`audit_events`; **Qdrant** as the at-scale vector escape hatch.

**Memory:** multi-layer (episodic/semantic/goal/project/relationship/timeline/reflection/preference) with **hybrid retrieval** (vector + structured + always-load), **composite ranking** (similarity·importance·recency·access·type − redundancy), async **extraction**, scheduled **consolidation/decay/reflection**, and **temporal evolution** with confidence + provenance.

**AI engine:** deterministic **6-step pipeline** (retrieve → understand → update → guide → ask → detect) with **tool-calling**, **layered cached prompts**, grounded in real coaching methodology, wrapped in **safety classifiers + escalation**.

**Auth/security:** **Clerk** (Google/X/Meta/email, MFA) → **WorkOS** for enterprise SSO; JWT verification seam; KMS field-level encryption for sensitive memory; Secrets Manager; rate limits + budgets; GDPR export/delete; audit log; zero-retention provider config.

**Cloud:** **AWS** — ECS Fargate → EKS at scale, RDS/Aurora, ElastiCache, S3, KMS, WAF; Docker, Kubernetes-ready.

This delivers the three pillars (Life Model, Memory, Coaching Engine), one client language and one AI language, a single durable datastore, model-agnostic AI, and a clean path to mobile and enterprise with minimal rewrites.

---

## 18. Repository Structure & Service Boundaries

### 18.1 Monorepo layout

```
life-coach/
├─ apps/
│  ├─ web/                    # Next.js (App Router, TS)
│  │  ├─ app/                 # routes: (auth), onboarding, coach, dashboard
│  │  ├─ components/          # uses @repo/ui
│  │  └─ lib/                 # uses @repo/api-client
│  └─ mobile/                 # Expo (React Native, TS)
│     ├─ app/                 # expo-router screens
│     └─ components/
├─ packages/
│  ├─ types/                  # zod schemas + TS types (mirrors OpenAPI)
│  ├─ api-client/             # generated typed client, auth, SSE
│  ├─ core/                   # shared logic: onboarding SM, formatting, validation
│  └─ ui/                     # design tokens, shared primitives
├─ services/
│  └─ api/                    # Python FastAPI service (the AI core)
│     ├─ app/
│     │  ├─ main.py
│     │  ├─ api/v1/           # routers: auth, onboarding, profile, goals,
│     │  │                    #          projects, sessions, memory, account
│     │  ├─ core/             # config, security (JWT), rate-limit, errors
│     │  ├─ db/               # SQLAlchemy models, session, RLS helpers
│     │  ├─ memory/           # storage, retrieval, ranking, consolidation
│     │  │  ├─ extraction.py  # LLM fact/goal extraction (schema-bound)
│     │  │  ├─ retrieval.py   # hybrid pipeline + budget assembler
│     │  │  ├─ ranking.py     # composite scoring + MMR
│     │  │  └─ consolidation.py
│     │  ├─ coaching/         # orchestrator (6-step pipeline), tools, prompts
│     │  │  ├─ orchestrator.py
│     │  │  ├─ tools.py
│     │  │  ├─ prompts/       # layered prompt templates
│     │  │  └─ methodology.py
│     │  ├─ onboarding/       # question graph + adaptive engine
│     │  ├─ llm/              # CoachLLM façade over LiteLLM, router, redaction
│     │  ├─ safety/           # classifiers, escalation, crisis resources
│     │  ├─ workers/          # Celery tasks + beat schedules
│     │  └─ schemas/          # Pydantic request/response (source for OpenAPI)
│     ├─ migrations/          # Alembic
│     └─ tests/               # unit + eval harness + safety red-team suite
├─ infra/
│  ├─ docker/                 # Dockerfiles (api, worker, web)
│  ├─ terraform/              # AWS: VPC, RDS, ElastiCache, ECS/EKS, KMS, S3, WAF
│  └─ k8s/                    # Helm charts / manifests (K8s-ready)
├─ packages-py/               # (optional) shared Python libs
├─ turbo.json
├─ pyproject.toml             # uv/poetry for services/api
└─ README.md
```

### 18.2 Service boundaries

- **`apps/web` & `apps/mobile`** — presentation only; no business logic beyond view state; talk to the backend via `@repo/api-client`. **No direct DB or LLM access.**
- **`services/api` (FastAPI)** — the only thing that touches Postgres, Redis, and LLM providers. Internally modular (`memory`, `coaching`, `onboarding`, `llm`, `safety`) so any module (esp. **memory**) can be extracted into its own service later without changing callers.
- **`workers`** — share the `services/api` codebase (models, memory, llm) but run as separate processes/containers; communicate only via the Redis broker and Postgres. No synchronous coupling to the API.
- **`llm` module** — the *only* place that knows about providers; everything else depends on the `CoachLLM` interface (model-agnostic).
- **`memory` module** — the *only* place that knows storage/retrieval internals; coaching depends on a `MemoryService` interface (pgvector → Qdrant swap stays local).
- **`infra`** — owns all cloud/runtime; apps/services declare needs via env/secrets, never hardcode infra.

### 18.3 Contracts between boundaries

- **Client ↔ API:** OpenAPI (generated from FastAPI/Pydantic) → `@repo/api-client` + `@repo/types`. Single source of truth; breaking changes caught at build.
- **API ↔ Workers:** typed Celery task signatures + idempotency keys; payloads are IDs, not large blobs.
- **API ↔ Providers:** `CoachLLM` interface (generate/stream/embed/tools) implemented over LiteLLM.
- **App ↔ DB:** SQLAlchemy models + Alembic migrations; RLS enforced; repository pattern per aggregate.

---

### Implementation phases (engineering sequence)

1. **P0:** monorepo + Turborepo, FastAPI skeleton, Postgres + Alembic + RLS, Clerk JWT verify, LiteLLM façade, Langfuse, CI with eval/safety stubs, Docker, Terraform baseline.
2. **P1a:** onboarding question graph + adaptive engine → Life Profile; schema for profile/domains/goals/projects/semantic_facts/episodic.
3. **P1b:** coaching orchestrator (6-step, lightweight), tools, layered prompts, SSE streaming, hybrid retrieval v1 (always-load + vector), async extraction worker.
4. **P1c:** web dashboard (profile/goals/projects), safety v1, export/delete + audit.
5. **P2:** ranking model + MMR, consolidation/decay/reflection jobs, belief-revision UX, Expo mobile app, weekly reviews.
6. **P3:** proactive nudges (Beat + push), life-change-detection actions, A/B + eval flywheel, scale hardening.
7. **P4:** WorkOS SSO/SCIM, integrations, org/coach-collab.

*End of document.*
