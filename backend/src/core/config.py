from typing import List, Optional
from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Financial SaaS Backend"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/financial_saas"
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/financial_saas"

    # Security
    SECRET_KEY: str = "change-this-insecure-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Storage
    STORAGE_DIR: str = "backend/storage"
    DOCUMENT_MAX_SIZE_BYTES: int = 25 * 1024 * 1024
    DOCUMENT_CONFIDENCE_THRESHOLD: float = 0.85
    DOCUMENT_EXTRACTION_PROVIDER: str = "local"

    # Hermes is an external operational client. Secrets are supplied only at
    # runtime; an unset token disables the machine endpoint.
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

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
