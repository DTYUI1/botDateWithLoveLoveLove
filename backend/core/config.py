"""
Конфигурация Backend API.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path


def _resolve_env_file():
    """Найти .env файл: сначала рядом с backend/, потом в cwd."""
    # backend/core/config.py -> backend/ -> project root
    backend_root = Path(__file__).parent.parent
    candidates = [
        backend_root / ".env",
        Path.cwd() / ".env",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://connectme_user:your_secure_password_here@db:5432/connectme_db",
    )

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0")

    # RabbitMQ
    rabbitmq_url: str = Field(
        default="amqp://guest:guest@rabbitmq:5672//",
    )

    # Minio
    minio_endpoint: str = Field(default="minio:9000")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket: str = Field(default="profile-photos")

    # Application
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")


settings = BackendSettings()
