from pathlib import Path
from typing import List, Optional

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Financial SaaS Backend"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/financial_saas"
    SYNC_DATABASE_URL: str = "postgresql://postgres:***@localhost:5432/financial_saas"
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, le=200)
    DB_POOL_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=300)
    DB_POOL_RECYCLE_SECONDS: int = Field(default=1800, ge=60, le=86400)

    # Security
    SECRET_KEY: str = "change-this-insecure-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Storage
    STORAGE_DIR: str = "backend/storage"
    DOCUMENT_MAX_SIZE_BYTES: int = 25 * 1024 * 1024
    DOCUMENT_CONFIDENCE_THRESHOLD: float = 0.85
    DOCUMENT_EXTRACTION_PROVIDER: str = "local"
    DOCUMENT_EXTRACTION_API_KEY: Optional[SecretStr] = None
    DOCUMENT_EXTRACTION_API_BASE: Optional[str] = None
    DOCUMENT_EXTRACTION_MODEL: Optional[str] = None
    DOCUMENT_EXTRACTION_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=120.0)
    DOCUMENT_EXTRACTION_MAX_TOKENS: int = Field(default=2000, ge=100, le=8000)

    # Hermes is an external operational client. Secrets are supplied only at runtime.
    HERMES_AGENT_TOKEN: Optional[str] = None
    HERMES_ORGANIZATION_ID: Optional[str] = None

    # Disabled without explicit webhook secrets; mock never contacts Meta.
    WHATSAPP_PROVIDER: str = "mock"
    WHATSAPP_VERIFY_TOKEN: Optional[SecretStr] = None
    WHATSAPP_WEBHOOK_APP_SECRET: Optional[SecretStr] = None
    WHATSAPP_API_TOKEN: Optional[SecretStr] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_GRAPH_VERSION: str = "v20.0"
    WHATSAPP_SAAS_URL: str = "https://localhost"
    WHATSAPP_ADAPTER_TOKEN: Optional[SecretStr] = None
    WHATSAPP_TENANT_TOKENS: dict[str, SecretStr] = Field(default_factory=dict)
    WHATSAPP_ORG_MESSAGES_PER_MINUTE: int = Field(default=200, ge=20)

    # Feature 008: no external egress is enabled by configuration.
    AI_INSIGHT_PROVIDER: str = "mock"
    AI_INSIGHT_API_KEY: Optional[SecretStr] = None
    AI_INSIGHT_CACHE_TTL_SECONDS: int = Field(default=3600, ge=1, le=3600)
    AI_INSIGHT_TIMEOUT_SECONDS: float = Field(default=0.2, gt=0, le=0.3)
    AI_INSIGHT_MAX_TOKENS: int = Field(default=500, ge=100, le=500)
    AI_INSIGHT_QA_MAX_TOKENS: int = Field(default=1000, ge=100, le=1000)

    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    @model_validator(mode="after")
    def validate_production_safety(self):
        if self.ENVIRONMENT.lower() not in {"production", "staging"}:
            return self
        errors = []
        if self.DEBUG:
            errors.append("DEBUG must be false")
        if len(self.SECRET_KEY) < 32 or self.SECRET_KEY == "change-this-insecure-secret-key-in-production":
            errors.append("SECRET_KEY must be a non-default secret of at least 32 characters")
        if "*" in self.BACKEND_CORS_ORIGINS:
            errors.append("BACKEND_CORS_ORIGINS must be an explicit allowlist")
        if not self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            errors.append("DATABASE_URL must use PostgreSQL asyncpg")
        if not self.SYNC_DATABASE_URL.startswith("postgresql://") or "***" in self.SYNC_DATABASE_URL:
            errors.append("SYNC_DATABASE_URL must contain a real PostgreSQL connection URL")
        if not Path(self.STORAGE_DIR).is_absolute():
            errors.append("STORAGE_DIR must be absolute")
        if errors:
            raise ValueError("Unsafe production configuration: " + "; ".join(errors))
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
