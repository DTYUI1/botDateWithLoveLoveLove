"""Celery tasks для рейтингов.

`recalculate_profile_rating` — точечный пересчёт рейтинга одного профиля
(не блокирует ночной полный пересчёт `recalculate_all_ratings`). Триггерится
из swipe_consumer'а / HTTP-эндпойнтов на горячем пути.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from sqlalchemy import select

from celery_app import celery_app, _build_behavioral_stats
from core.database import async_session_factory
from core.redis_client import get_redis_client
from models.profile import Profile
from services.rating_service import RatingService


async def _recalculate_one(profile_id: Any) -> dict:
    async with async_session_factory() as session:
        result = await session.execute(select(Profile).where(Profile.id == profile_id))
        profile = result.scalar_one_or_none()
        if profile is None:
            logger.warning(f"[Celery rating] профиль {profile_id} не найден")
            return {"status": "not_found", "profile_id": str(profile_id)}

        try:
            redis_client = await get_redis_client()
            rating_cache = redis_client.get_rating_cache()
        except Exception as e:
            logger.warning(f"[Celery rating] Redis недоступен: {e}")
            rating_cache = None

        service = RatingService(session, rating_cache=rating_cache)
        stats = await _build_behavioral_stats(session, profile)
        ratings = await service.calculate_all_ratings(profile, stats)
        await service.upsert_rating_in_session(profile.id, ratings["combined"])
        await session.commit()
        return {
            "status": "ok",
            "profile_id": str(profile.id),
            "combined": ratings["combined"],
        }


@celery_app.task(name="backend.recalculate_profile_rating")
def recalculate_profile_rating(profile_id: Any) -> dict:
    """Точечный пересчёт комбинированного рейтинга одного профиля."""
    return asyncio.run(_recalculate_one(profile_id))
