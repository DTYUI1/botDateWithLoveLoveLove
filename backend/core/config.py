"""
Конфигурация Backend API.
"""

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
        default="postgresql+asyncpg://REQUIRED_POSTGRES_USER:REQUIRED_POSTGRES_PASSWORD@db:5432/REQUIRED_POSTGRES_DB",
    )

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0")
    celery_broker_url: str | None = Field(default=None)
    celery_result_backend: str | None = Field(default=None)

    # RabbitMQ
    rabbitmq_url: str = Field(
        default="amqp://REQUIRED_RABBITMQ_USER:REQUIRED_RABBITMQ_PASSWORD@rabbitmq:5672//",
    )

    # Minio
    minio_endpoint: str = Field(default="minio:9000")
    minio_access_key: str = Field(default="REQUIRED_MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="REQUIRED_MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="profile-photos")
    minio_secure: bool = Field(default=False)
    minio_presigned_expiry_seconds: int = Field(default=3600)

    # Application
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")


settings = BackendSettings()
