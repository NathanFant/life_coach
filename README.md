# AI Life Coach

A coach that builds a **structured, evolving model of your life** and helps you make
continuous progress across career, business, family, finances, habits, and growth.
Not general chat — memory-grounded, goal-oriented coaching.

> 📐 **Full technical design:** [docs/DESIGN.md](docs/DESIGN.md) — architecture, memory
> system, AI orchestration, security, mobile strategy, roadmap, costs, and scaling.

## Architecture at a glance

- **Web:** Next.js (App Router) + TypeScript — `apps/web`
- **Mobile:** Expo (React Native), iOS + Android — `apps/mobile`
- **AI core:** Python + FastAPI — `services/api` (the only thing touching DB/Redis/LLMs)
- **Shared TS:** `packages/{types,api-client,core,ui}`
- **Data:** PostgreSQL 16 + pgvector · **Cache/queue:** Redis + Celery
- **LLMs:** OpenAI / Anthropic / Gemini via a model-agnostic LiteLLM façade
- **Auth:** Clerk (Google/X/Meta/email) → WorkOS for enterprise SSO later

## Repository layout

```
apps/        web (Next.js) · mobile (Expo)
packages/    types · api-client · core · ui   (shared TypeScript)
services/    api  (FastAPI: memory, coaching, onboarding, llm, safety, workers)
infra/       docker (local) · terraform (AWS) · k8s
docs/        DESIGN.md  (the source of truth for this build)
```

## Getting started (local)

```bash
# 1. Start datastores (Postgres + pgvector, Redis)
docker compose -f infra/docker/docker-compose.yml up -d

# 2. Backend (FastAPI AI core)
cp .env.example .env            # fill in provider + Clerk keys
uv --project services/api run uvicorn app.main:app --reload --port 8000
#   → http://localhost:8000/health  ·  /docs for OpenAPI

# 3. Frontends (from repo root)
corepack enable pnpm
pnpm install
pnpm --filter web dev           # http://localhost:3000
pnpm --filter mobile dev        # Expo
```

## Status

**Scaffold only** — structure, configs, and service boundaries are in place; business
logic is stubbed (endpoints return `501`). Implementation follows the phased plan in
[docs/DESIGN.md §11–§13](docs/DESIGN.md). Start with Phase 0 (foundations) → Phase 1 (MVP).
