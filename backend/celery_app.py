"""
Celery app для фоновых backend-задач ConnectMe.

Запуск worker:
    celery -A celery_app.celery_app worker -l info

Запуск beat:
    celery -A celery_app.celery_app beat -l info
"""

import asyncio
from datetime import date, datetime
from typing import Optional

from celery import Celery
from celery.schedules import crontab
from loguru import logger
from sqlalchemy import and_, func, or_, select

from core.config import settings
from core.database import async_session_factory
from core.redis_client import get_redis_client
from models.match import Match
from models.message import Message
from models.profile import Profile
from models.swipe import Swipe
from models.user import User
from services.rating_service import RatingService


broker_url = settings.celery_broker_url or settings.redis_url
result_backend = settings.celery_result_backend or settings.redis_url

celery_app = Celery(
    "connectme_backend",
    broker=broker_url,
    backend=result_backend,
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    beat_schedule={
        "recalculate-ratings-daily": {
            "task": "backend.recalculate_all_ratings",
            "schedule": crontab(hour=3, minute=0),
            "args": (),
        },
    },
)


async def _count_scalar(session, statement) -> int:
    result = await session.execute(statement)
    return result.scalar() or 0


async def _build_behavioral_stats(session, profile: Profile) -> dict:
    """Собрать статистику поведения профиля для рейтинга."""
    likes_received = await _count_scalar(
        session,
        select(func.count(Swipe.id)).where(
            Swipe.swiped_id == profile.id,
            Swipe.action.in_(["like", "super_like"]),
        ),
    )
    passes_received = await _count_scalar(
        session,
        select(func.count(Swipe.id)).where(
            Swipe.swiped_id == profile.id,
            Swipe.action == "pass",
        ),
    )
    total_swipes = await _count_scalar(
        session,
        select(func.count(Swipe.id)).where(Swipe.swiper_id == profile.id),
    )
    matches_count = await _count_scalar(
        session,
        select(func.count(Match.id)).where(
            Match.status == "active",
            or_(Match.profile1_id == profile.id, Match.profile2_id == profile.id),
        ),
    )
    messages_sent = await _count_scalar(
        session,
        select(func.count(Message.id)).where(
            Message.sender_id == profile.id,
            Message.deleted_at.is_(None),
        ),
    )

    user_result = await session.execute(select(User).where(User.id == profile.user_id))
    user = user_result.scalar_one_or_none()
    now = datetime.utcnow()
    created_at = profile.created_at.replace(tzinfo=None) if profile.created_at else now
    last_active_at = user.last_active_at if user and user.last_active_at else profile.updated_at
    last_active_at = last_active_at.replace(tzinfo=None) if last_active_at else now

    return {
        "like_received_count": likes_received,
        "pass_received_count": passes_received,
        "matches_count": matches_count,
        "total_swipes": total_swipes,
        "messages_sent": messages_sent,
        "days_active": max((now.date() - created_at.date()).days, 1),
        "last_active_days_ago": max((now.date() - last_active_at.date()).days, 0),
        "referral_bonus": 0.0,
    }


async def _recalculate_all_ratings(limit: Optional[int] = None) -> dict:
    async with async_session_factory() as session:
        query = select(Profile).where(Profile.is_active == True).order_by(Profile.created_at.asc())
        if limit:
            query = query.limit(limit)

        result = await session.execute(query)
        profiles = result.scalars().all()

        try:
            redis_client = await get_redis_client()
            rating_cache = redis_client.get_rating_cache()
        except Exception as e:
            logger.warning(f"[Celery] Redis rating cache недоступен: {e}")
            rating_cache = None

        service = RatingService(session, rating_cache=rating_cache)
        recalculated = 0

        for profile in profiles:
            stats = await _build_behavioral_stats(session, profile)
            ratings = await service.calculate_all_ratings(profile, stats)
            await service.upsert_rating_in_session(profile.id, ratings["combined"])
            recalculated += 1

        await session.commit()
        logger.info(f"[Celery] Пересчитано рейтингов: {recalculated}")
        return {
            "status": "ok",
            "date": date.today().isoformat(),
            "recalculated": recalculated,
        }


@celery_app.task(name="backend.recalculate_all_ratings")
def recalculate_all_ratings(limit: Optional[int] = None) -> dict:
    """Celery task: пересчитать комбинированный рейтинг активных профилей."""
    return asyncio.run(_recalculate_all_ratings(limit=limit))
