"""
Redis клиент для Backend API.

Реализует:
- Async подключение к Redis
- Health check
- Factory для создания кэшей
"""

from typing import Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from core.config import settings
from infrastructure.redis.cache_patterns import (
    ProfileSessionCache,
    RatingCache,
    SwipeCounterCache,
)


class RedisClient:
    """
    Async Redis клиент.
    
    Usage:
        client = RedisClient()
        await client.connect()
        
        # Получить кэши
        session_cache = client.get_session_cache()
        rating_cache = client.get_rating_cache()
        swipe_counter = client.get_swipe_counter()
    """

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.redis_url
        self.redis: Optional[Redis] = None

    async def connect(self):
        """Подключение к Redis."""
        self.redis = redis.from_url(
            self.redis_url,
            decode_responses=True,
            max_connections=10,
        )
        # Проверить подключение
        await self.redis.ping()

    async def disconnect(self):
        """Отключение от Redis."""
        if self.redis:
            await self.redis.close()

    async def health_check(self) -> bool:
        """Проверка здоровья Redis."""
        try:
            if not self.redis:
                await self.connect()
            return await self.redis.ping()
        except Exception:
            return False

    def get_session_cache(self) -> ProfileSessionCache:
        """Получить кэш сессий."""
        if not self.redis:
            raise RuntimeError("Redis не подключен. Вызовите connect()")
        return ProfileSessionCache(self.redis)

    def get_rating_cache(self) -> RatingCache:
        """Получить кэш рейтингов."""
        if not self.redis:
            raise RuntimeError("Redis не подключен. Вызовите connect()")
        return RatingCache(self.redis)

    def get_swipe_counter(self) -> SwipeCounterCache:
        """Получить счётчик свайпов."""
        if not self.redis:
            raise RuntimeError("Redis не подключен. Вызовите connect()")
        return SwipeCounterCache(self.redis)

    async def get_client(self) -> Redis:
        """Получить raw Redis клиент."""
        if not self.redis:
            await self.connect()
        return self.redis

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# Singleton для удобного доступа
redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """Получить singleton Redis клиент."""
    global redis_client
    if redis_client is None:
        redis_client = RedisClient()
        await redis_client.connect()
    return redis_client


async def close_redis_client():
    """Закрыть singleton Redis клиент."""
    global redis_client
    if redis_client:
        await redis_client.disconnect()
        redis_client = None
