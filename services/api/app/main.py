"""
FastAPI application entrypoint — the AI Life Coach core.

The only process that touches Postgres, Redis, and LLM providers.
Internally modular so the memory layer can be extracted to its own service later.

Startup order:
  1. configure_logging()   — structlog JSON/pretty setup
  2. configure_langfuse_litellm_callback()  — LLM tracing (no-op if keys absent)
  3. Register routers
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.tracing import configure_langfuse_litellm_callback

configure_logging()

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_langfuse_litellm_callback()
    yield
    # Flush any pending Langfuse traces on shutdown
    from app.core.tracing import get_tracer

    get_tracer().flush()


app = FastAPI(
    title="AI Life Coach API",
    version="0.1.0",
    description=(
        "Memory-grounded coaching engine. "
        "See [docs/DESIGN.md](https://github.com/NathanFant/life_coach/blob/main/docs/DESIGN.md)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/v1")


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
