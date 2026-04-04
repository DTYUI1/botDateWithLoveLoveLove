"""
API роутер для работы с профилями.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from core.database import get_db
from schemas.profile import ProfileCreate, ProfileUpdate, ProfileResponse
from services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=Optional[ProfileResponse])
async def get_profile(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """Получить профиль пользователя."""
    logger.info(f"[Backend Profile] GET /profile telegram_id={telegram_id}")
    try:
        service = ProfileService(db)
        profile = await service.get_profile_by_telegram_id(telegram_id)
        logger.info(f"[Backend Profile] Профиль: {'НАЙДЕН' if profile else 'НЕТ'}")

        if not profile:
            return None

        return profile
    except Exception as e:
        logger.error(f"[Backend Profile] ОШИБКА: {type(e).__name__}: {e}")
        raise


@router.post("", response_model=ProfileResponse)
async def create_profile(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    profile_data: ProfileCreate = ...,
    db: AsyncSession = Depends(get_db),
):
    """Создать профиль пользователя."""
    service = ProfileService(db)

    try:
        profile = await service.create_profile(telegram_id, profile_data)
        await db.commit()
        return profile
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("", response_model=ProfileResponse)
async def update_profile(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    profile_data: ProfileUpdate = ...,
    db: AsyncSession = Depends(get_db),
):
    """Обновить профиль пользователя."""
    service = ProfileService(db)

    profile = await service.update_profile(telegram_id, profile_data)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    await db.commit()
    return profile
