"""
API роутер для matching (свайпы, получение анкет, мэтчи).

Интегрирует:
- MatchingService для подбора анкет
- Redis кэширование (ProfileSessionCache)
- ProfileService для записи свайпов и мэтчей
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from core.database import get_db
from core.redis_client import get_redis_client
from core.mq import safe_publish
from core.metrics import CACHE_HITS, CACHE_MISSES, SWIPES_TOTAL, MATCHES_TOTAL, SWIPE_DURATION
from schemas.match import SwipeRequest, SwipeResponse, MatchResponse
from schemas.profile import ProfileShort
from services.profile_service import ProfileService
from services.matching_service import MatchingService

router = APIRouter(prefix="/matching", tags=["matching"])


@router.get("/next", response_model=Optional[ProfileShort])
async def get_next_profile(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    session_id: Optional[str] = Query(None, description="ID сессии кэша"),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить следующую анкету для свайпа.
    
    Приоритет:
    1. Redis кэш (если сессия активна)
    2. MatchingService (подбор из БД с рейтингом)
    3. ProfileService (fallback без рейтинга)
    """
    logger.info(f"[Backend Matching] GET /matching/next telegram_id={telegram_id}")
    
    try:
        # Пробуем получить из Redis кэша; при сбое продолжаем подбор из БД.
        session_cache = None
        try:
            redis_client = await get_redis_client()
            session_cache = redis_client.get_session_cache()
        except Exception as e:
            CACHE_MISSES.labels(cache="profile_session").inc()
            logger.warning(f"[Backend Matching] Redis cache недоступен: {type(e).__name__}: {e}")
        
        if session_id and session_cache:
            # Проверяем, есть ли закэшированные анкеты
            is_cached = await session_cache.is_session_cached(telegram_id, session_id)
            if is_cached:
                profile_data = await session_cache.get_next_profile(telegram_id, session_id)
                if profile_data:
                    CACHE_HITS.labels(cache="profile_session").inc()
                    remaining = await session_cache.get_remaining_count(telegram_id, session_id)
                    logger.info(f"[Backend Matching] ✅ Анкета из кэша, осталось: {remaining}")
                    return ProfileShort(**profile_data)
            CACHE_MISSES.labels(cache="profile_session").inc()
        elif session_id:
            CACHE_MISSES.labels(cache="profile_session").inc()
        
        # Кэш пуст или нет session_id — подбираем анкеты
        matching_service = MatchingService(db, session_cache)
        result = await matching_service.start_matching_session(telegram_id, session_id)
        
        profiles = result.get("profiles", [])
        if not profiles:
            # Анкеты, прошедшие фильтры, действительно закончились — не подменяем
            # их рандомом без looking_for/возрастного фильтра.
            logger.info("[Backend Matching] Подходящих анкет нет (фильтры исчерпаны)")
            return None
        
        # Возвращаем первую анкету из подобранных
        first_profile = profiles[0]
        return ProfileShort(
            id=UUID(first_profile["id"]),
            display_name=first_profile.get("display_name"),
            age=first_profile.get("age"),
            city=first_profile.get("city"),
            bio=first_profile.get("bio"),
            interests=first_profile.get("interests", []),
            primary_photo_url=first_profile.get("primary_photo_url"),
            username=first_profile.get("username"),
        )
        
    except Exception as e:
        logger.error(f"[Backend Matching] ОШИБКА get_next_profile: {type(e).__name__}: {e}")
        return None


@router.post("/swipe", response_model=SwipeResponse)
async def swipe_profile(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    swipe_data: SwipeRequest = ...,
    db: AsyncSession = Depends(get_db),
):
    """Отправить свайп (лайк/пропуск) анкете."""
    logger.info(f"[Backend Matching] POST /matching/swipe telegram_id={telegram_id}, action={swipe_data.action}")

    service = ProfileService(db)

    # Находим профиль пользователя
    user_profile = await service.get_profile_by_telegram_id(telegram_id)
    if not user_profile:
        raise HTTPException(status_code=404, detail="Профиль не найден. Создайте анкету.")

    with SWIPE_DURATION.time():
        result = await service.record_swipe(
            swiper_id=user_profile.id,
            swiped_id=swipe_data.profile_id,
            action=swipe_data.action,
        )
        await db.commit()

    SWIPES_TOTAL.labels(action=swipe_data.action).inc()
    if result.get("is_match"):
        MATCHES_TOTAL.inc()

    await _publish_swipe_events(
        swiper_id=user_profile.id,
        swiped_id=swipe_data.profile_id,
        action=swipe_data.action,
        result=result,
    )

    # Celery: точечный пересчёт рейтинга получателя свайпа.
    # При is_match — единственный match.created для bot consumer публикует
    # send_match_push, чтобы не задублировать push-уведомления.
    try:
        from tasks.rating_tasks import recalculate_profile_rating
        recalculate_profile_rating.delay(profile_id=str(swipe_data.profile_id))
    except Exception as e:
        logger.warning(f"[Backend Matching] Celery rating task не отправлена: {e}")

    if result.get("is_match") and result.get("match_id"):
        try:
            from tasks.notification_tasks import send_match_push
            send_match_push.delay(
                match_id=str(result["match_id"]),
                user1_id=str(user_profile.id),
                user2_id=str(swipe_data.profile_id),
            )
        except Exception as e:
            logger.warning(f"[Backend Matching] Celery match push не отправлен: {e}")

    logger.info(f"[Backend Matching] Свайп записан, is_match={result['is_match']}")
    return SwipeResponse(**result)


@router.get("/matches", response_model=List[MatchResponse])
async def get_matches(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """Получить список мэтчей пользователя."""
    logger.info(f"[Backend Matching] GET /matching/matches telegram_id={telegram_id}")
    
    service = ProfileService(db)
    matches = await service.get_matches(telegram_id)
    return matches


@router.post("/session/refresh", response_model=dict)
async def refresh_matching_session(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    session_id: Optional[str] = Query(None, description="ID сессии кэша"),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновить сессию подбора анкет.
    
    Перезагружает анкеты из БД с учётом новых свайпов.
    """
    logger.info(f"[Backend Matching] POST /matching/session/refresh telegram_id={telegram_id}")
    
    try:
        redis_client = await get_redis_client()
        session_cache = redis_client.get_session_cache()
        
        matching_service = MatchingService(db, session_cache)
        result = await matching_service.refresh_session(telegram_id, session_id)
        
        return result
    except Exception as e:
        logger.error(f"[Backend Matching] ОШИБКА refresh_session: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить сессию")


@router.get("/session/status", response_model=dict)
async def get_session_status(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    session_id: str = Query(..., description="ID сессии кэша"),
):
    """Получить статус сессии подбора."""
    try:
        redis_client = await get_redis_client()
        session_cache = redis_client.get_session_cache()
        
        is_cached = await session_cache.is_session_cached(telegram_id, session_id)
        remaining = 0
        if is_cached:
            remaining = await session_cache.get_remaining_count(telegram_id, session_id)
        
        return {
            "telegram_id": telegram_id,
            "session_id": session_id,
            "is_cached": is_cached,
            "remaining_profiles": remaining,
        }
    except Exception as e:
        logger.error(f"[Backend Matching] ОШИБКА session_status: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось получить статус")


async def _publish_swipe_events(
    swiper_id,
    swiped_id,
    action: str,
    result: dict,
) -> None:
    """Опубликовать swipe-событие через singleton publisher.

    Полностью fail-safe: ошибки публикации не валят основной HTTP-ответ
    (см. `core.mq.safe_publish`). При недоступности RabbitMQ запрос всё
    равно завершится 200.
    """
    swipe_id = result.get("swipe_id")
    await safe_publish(
        lambda p: p.publish_swipe_event(
            from_user_id=swiper_id,
            to_user_id=swiped_id,
            action=action,
            swipe_id=swipe_id,
        ),
        op="swipe_event",
    )
