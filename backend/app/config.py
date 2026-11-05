from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger("agenthub.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "AgentHub"
    version: str = "0.1.0"
    app_mode: str = "local"

    database_url: str = "sqlite+aiosqlite:///./data/agenthub.db"
    db_echo: bool = False
    redis_url: str = "redis://127.0.0.1:6379/0"

    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30

    secret_encryption_key: str = ""

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    ollama_base_url: str = "http://127.0.0.1:11434"
    llm_timeout_seconds: float = 120.0

    bootstrap_admin_email: str = "admin@agenthub.local"
    bootstrap_admin_password: str = "admin12345"
    bootstrap_admin_name: str = "AgentHub Admin"

    seed_demo_data: bool = True
    log_level: str = "INFO"

    @field_validator("app_mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"local", "docker"}:
            raise ValueError("APP_MODE must be either 'local' or 'docker'")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_docker_mode(self) -> bool:
        return self.app_mode == "docker"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    if settings.jwt_secret.startswith("dev-only"):
        logger.warning("JWT_SECRET is the development default; set it for anything public")
    return settings


def reset_settings_cache() -> None:
    get_settings.cache_clear()
