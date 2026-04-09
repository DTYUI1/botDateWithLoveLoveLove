"""
API роутер для работы с рейтингами.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from loguru import logger

from core.database import get_db
from core.redis_client import get_redis_client
from models.user import User
from models.profile import Profile
from models.rating import RatingCombined as RatingCombinedModel
from schemas.rating import RatingResponse
from services.profile_service import ProfileService

router = APIRouter(prefix="/rating", tags=["rating"])


@router.get("/my", response_model=RatingResponse)
async def get_my_rating(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить рейтинг пользователя.
    
    Возвращает:
    - primary_score: Первичный рейтинг (заполненность профиля)
    - behavioral_score: Поведенческий рейтинг (активность)
    - total_score: Комбинированный рейтинг
    - tier: Уровень (S, A, B, C, D, E)
    - percentile: Перцентиль среди всех пользователей
    - rank_position: Позиция в рейтинге
    """
    logger.info(f"[Backend Rating] GET /rating/my telegram_id={telegram_id}")
    
    try:
        # Находим профиль пользователя
        user_result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        profile_result = await db.execute(
            select(Profile).where(Profile.user_id == user.id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден. Создайте анкету.")
        
        # Получаем комбинированный рейтинг
        rating_result = await db.execute(
            select(RatingCombinedModel).where(
                RatingCombinedModel.profile_id == profile.id
            )
        )
        rating = rating_result.scalar_one_or_none()
        
        if not rating:
            # Рейтинг ещё не рассчитан
            return RatingResponse(
                primary_score=0.0,
                behavioral_score=0.0,
                total_score=0.0,
                tier="E",
                percentile=None,
                rank_position=None,
                calculated_at=None,
            )
        
        # Проверяем кэш рейтинга в Redis
        try:
            redis_client = await get_redis_client()
            rating_cache = redis_client.get_rating_cache()
            cached_score = await rating_cache.get_user_score("combined", telegram_id)
            # Если есть в кэше, используем его для актуальности
            if cached_score is not None:
                total_score = cached_score
            else:
                total_score = float(rating.total_score)
        except Exception:
            total_score = float(rating.total_score)
        
        return RatingResponse(
            primary_score=float(rating.primary_score),
            behavioral_score=float(rating.behavioral_score),
            total_score=total_score,
            tier=rating.tier,
            percentile=float(rating.percentile) if rating.percentile else None,
            rank_position=rating.rank_position,
            calculated_at=rating.calculated_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Backend Rating] ОШИБКА get_my_rating: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось получить рейтинг")
