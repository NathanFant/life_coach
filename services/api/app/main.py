"""FastAPI application entrypoint — the AI Life Coach core.

The only process that touches Postgres, Redis, and LLM providers (docs/DESIGN.md §18.2).
Internally modular so the memory layer can be extracted to its own service later.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="AI Life Coach API",
    version="0.1.0",
    description="Memory-grounded coaching engine. See docs/DESIGN.md.",
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
