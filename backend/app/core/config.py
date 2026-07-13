from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Aegis AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Default: Docker Compose (localhost); override with env vars for K8s
    # kubectl creates aegis-secrets with DATABASE_URL = postgresql+asyncpg://postgres:<pw>@postgres:5432/aegis
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aegis"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    LOG_LEVEL: str = "INFO"

    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7

    # Hardcoded limit replacements (Milestone 7)
    REPOSITORY_FILE_LIMIT: int = 200
    BATCH_FILE_LIMIT: int = 500
    FILE_PREVIEW_LIMIT: int = 50
    FILE_PREVIEW_CHARS: int = 300
    CONTEXT_TRUNCATION_LIMIT: int = 30
    SIMILARITY_THRESHOLD: float = 0.3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()