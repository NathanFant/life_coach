"""Application configuration, loaded from environment (see /.env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "info"

    # Datastores
    database_url: str = "postgresql+psycopg://coach:coach@localhost:5432/lifecoach"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Auth (Clerk) — backend verifies JWTs via JWKS.
    # CLERK_ISSUER is optional: Clerk does not expose the issuer value in the
    # dashboard. When absent, issuer validation is skipped (signature + expiry
    # still verified). Set it to the Clerk frontend API URL if you want the
    # extra check (format: https://<slug>.clerk.accounts.dev).
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""  # optional — leave blank to skip issuer validation

    # LLM routing (model-agnostic; see docs/DESIGN.md §6.1)
    coach_model: str = "anthropic/claude-sonnet-4-6"
    extraction_model: str = "anthropic/claude-haiku-4-5-20251001"
    embedding_model: str = "openai/text-embedding-3-small"

    # CORS
    api_cors_origins: str = "http://localhost:3000,http://localhost:8081"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
