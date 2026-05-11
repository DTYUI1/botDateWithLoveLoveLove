"""Singleton-доступ к MinIO-клиенту.

MinIOClient теперь создаётся один раз на lifespan приложения и переиспользуется
во всех запросах. Это убирает накладные расходы на пересоздание клиента
(включая инициализацию HTTP-пула minio sdk) на горячем пути загрузки фото.
"""

from __future__ import annotations

from typing import Optional

from infrastructure.minio.minio_client import MinIOClient

from core.config import settings


_client: Optional[MinIOClient] = None


def init_minio_client() -> MinIOClient:
    """Инициализировать singleton (вызвать один раз в startup)."""
    global _client
    if _client is None:
        _client = MinIOClient(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket_name=settings.minio_bucket,
            secure=settings.minio_secure,
        )
    return _client


def get_minio_client() -> MinIOClient:
    """FastAPI dependency: вернуть инициализированный singleton.

    Если клиент не был инициализирован (например, MinIO упал на startup),
    инициализируем лениво — это даёт self-heal после восстановления сервиса.
    """
    if _client is None:
        return init_minio_client()
    return _client


def reset_minio_client() -> None:
    """Только для тестов."""
    global _client
    _client = None
