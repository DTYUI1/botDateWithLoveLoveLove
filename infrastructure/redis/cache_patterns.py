"""
Patteрны кэширования для ConnectMe.

Реализует три основных паттерна:
1. ProfileSessionCache — кэш 10 анкет для свайп-сессии
2. RatingCache — кэш рейтингов (Sorted Set)
3. SwipeCounterCache — счётчики свайпов за день
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime

import redis.asyncio as redis


class ProfileSessionCache:
    """
    Кэш анкет для свайп-сессии пользователя.
    
    Хранит до 10 анкет на сессию в Redis List.
    Ключ: ranked_profiles:{user_id}:{session_id}
    TTL: 3600 секунд (1 час)
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def cache_profiles(
        self,
        user_id: int,
        session_id: str,
        profiles: List[Dict[str, Any]],
        ttl: int = 3600
    ):
        """
        Закэшировать анкеты для сессии.
        
        Args:
            user_id: ID пользователя
            session_id: ID сессии
            profiles: Список анкет (до 10)
            ttl: Время жизни кэша в секундах
        """
        key = f"ranked_profiles:{user_id}:{session_id}"

        async with self.redis.pipeline() as pipe:
            # Удалить старые данные
            await pipe.delete(key)
            # Добавить анкеты в список (FIFO)
            for profile in profiles:
                await pipe.rpush(key, json.dumps(profile, default=str))
            # Установить TTL
            await pipe.expire(key, ttl)
            await pipe.execute()

    async def get_next_profile(
        self,
        user_id: int,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Получить следующую анкету из кэша (LPOP)."""
        key = f"ranked_profiles:{user_id}:{session_id}"
        profile_json = await self.redis.lpop(key)

        if profile_json:
            return json.loads(profile_json)
        return None

    async def get_remaining_count(
        self,
        user_id: int,
        session_id: str
    ) -> int:
        """Получить количество оставшихся анкет в кэше."""
        key = f"ranked_profiles:{user_id}:{session_id}"
        return await self.redis.llen(key)

    async def clear_session(self, user_id: int, session_id: str):
        """Очистить сессию."""
        key = f"ranked_profiles:{user_id}:{session_id}"
        await self.redis.delete(key)

    async def is_session_cached(
        self,
        user_id: int,
        session_id: str
    ) -> bool:
        """Проверить, закэширована ли сессия."""
        key = f"ranked_profiles:{user_id}:{session_id}"
        return await self.redis.exists(key) > 0


class RatingCache:
    """
    Кэш рейтингов пользователей для быстрого подбора.
    
    Использует Sorted Set для ранжирования по score.
    Ключ: ratings:{type}
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def update_rating(
        self,
        rating_type: str,
        user_id: int,
        combined_score: float
    ):
        """
        Обновить рейтинг пользователя в Sorted Set.
        
        Args:
            rating_type: Тип рейтинга (primary, behavioral, combined)
            user_id: ID пользователя
            combined_score: Score для сортировки
        """
        key = f"ratings:{rating_type}"
        await self.redis.zadd(key, {str(user_id): combined_score})

    async def batch_update_ratings(
        self,
        rating_type: str,
        ratings: Dict[int, float]
    ):
        """
        Массовое обновление рейтингов.
        
        Args:
            rating_type: Тип рейтинга
            ratings: Dict {user_id: score}
        """
        key = f"ratings:{rating_type}"
        string_mapping = {str(user_id): score for user_id, score in ratings.items()}
        await self.redis.zadd(key, string_mapping)

    async def get_top_profiles(
        self,
        rating_type: str,
        min_score: float = 0.0,
        limit: int = 100
    ) -> List[int]:
        """
        Получить ID профилей с высоким рейтингом.
        
        Args:
            rating_type: Тип рейтинга
            min_score: Минимальный score
            limit: Максимальное количество
        """
        key = f"ratings:{rating_type}"
        results = await self.redis.zrevrangebyscore(
            key,
            max=100.0,
            min=min_score,
            start=0,
            num=limit
        )
        return [int(user_id) for user_id in results]

    async def get_user_rank(
        self,
        rating_type: str,
        user_id: int
    ) -> int:
        """Получить позицию пользователя в рейтинге (1-based)."""
        key = f"ratings:{rating_type}"
        rank = await self.redis.zrevrank(key, str(user_id))
        return rank + 1 if rank is not None else 0

    async def get_user_score(
        self,
        rating_type: str,
        user_id: int
    ) -> Optional[float]:
        """Получить score пользователя."""
        key = f"ratings:{rating_type}"
        score = await self.redis.zscore(key, str(user_id))
        return score

    async def clear_rating_type(self, rating_type: str):
        """Очистить весь рейтинг."""
        key = f"ratings:{rating_type}"
        await self.redis.delete(key)


class SwipeCounterCache:
    """
    Кэш счётчиков свайпов за день.
    
    Использует Hash для хранения статистики.
    Ключ: swipes:daily:{user_id}:{date}
    TTL: 86400 секунд (24 часа)
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def increment_swipe(
        self,
        user_id: int,
        action: str,  # 'like', 'pass', 'super_like'
        date: str = None
    ):
        """
        Увеличить счётчик свайпов.
        
        Args:
            user_id: ID пользователя
            action: Тип действия
            date: Дата в формате YYYY-MM-DD
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        key = f"swipes:daily:{user_id}:{date}"
        await self.redis.hincrby(key, action, 1)
        await self.redis.expire(key, 86400)  # 24 часа

    async def get_swipe_stats(
        self,
        user_id: int,
        date: str = None
    ) -> Dict[str, int]:
        """
        Получить статистику свайпов за день.
        
        Args:
            user_id: ID пользователя
            date: Дата в формате YYYY-MM-DD
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        key = f"swipes:daily:{user_id}:{date}"
        stats = await self.redis.hgetall(key)
        
        return {
            "like": int(stats.get("like", 0)),
            "pass": int(stats.get("pass", 0)),
            "super_like": int(stats.get("super_like", 0))
        }

    async def get_total_swipes(
        self,
        user_id: int,
        date: str = None
    ) -> int:
        """Получить общее количество свайпов за день."""
        stats = await self.get_swipe_stats(user_id, date)
        return sum(stats.values())

    async def has_reached_limit(
        self,
        user_id: int,
        limit: int,
        date: str = None
    ) -> bool:
        """Проверить, достиг ли пользователь лимита свайпов."""
        total = await self.get_total_swipes(user_id, date)
        return total >= limit

    async def reset_daily_counters(self, user_id: int, date: str = None):
        """Сбросить дневные счётчики."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        key = f"swipes:daily:{user_id}:{date}"
        await self.redis.delete(key)
