"""
API роутер для работы с настройками поиска.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from core.database import get_db
from models.user import User
from models.profile import Profile
from schemas.settings import SettingsResponse, SettingsUpdate
from services.profile_service import ProfileService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить настройки поиска пользователя.
    
    Возвращает текущие предпочтения:
    - Диапазон возраста (age_range_min, age_range_max)
    - Максимальное расстояние (distance_max_km)
    - Кого ищет (looking_for)
    - Город (city)
    """
    logger.info(f"[Backend Settings] GET /settings telegram_id={telegram_id}")
    
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
        
        return SettingsResponse(
            age_range_min=profile.age_range_min,
            age_range_max=profile.age_range_max,
            distance_max_km=profile.distance_max_km,
            looking_for=profile.looking_for,
            city=profile.city,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Backend Settings] ОШИБКА get_settings: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось получить настройки")


@router.put("", response_model=SettingsResponse)
async def update_settings(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    settings_data: SettingsUpdate = ...,
    db: AsyncSession = Depends(get_db),
):
    """
    Обновить настройки поиска пользователя.
    
    Можно изменить:
    - Диапазон возраста
    - Максимальное расстояние
    - Кого ищет
    - Город
    
    После обновления настрое кэш анкет сбрасывается.
    """
    logger.info(f"[Backend Settings] PUT /settings telegram_id={telegram_id}")
    
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
        
        # Обновляем поля настроек
        update_data = settings_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)
        
        await db.commit()
        await db.refresh(profile)
        
        logger.info(f"[Backend Settings] ✅ Настройки обновлены: {update_data.keys()}")
        
        return SettingsResponse(
            age_range_min=profile.age_range_min,
            age_range_max=profile.age_range_max,
            distance_max_km=profile.distance_max_km,
            looking_for=profile.looking_for,
            city=profile.city,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Backend Settings] ОШИБКА update_settings: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить настройки")
