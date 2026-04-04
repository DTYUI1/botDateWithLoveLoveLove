"""
API роутер для matching (свайпы, получение анкет, мэтчи).
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from schemas.match import SwipeRequest, SwipeResponse, MatchResponse
from schemas.profile import ProfileShort
from services.profile_service import ProfileService

router = APIRouter(prefix="/matching", tags=["matching"])


@router.get("/next", response_model=Optional[ProfileShort])
async def get_next_profile(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """Получить следующую анкету для свайпа."""
    service = ProfileService(db)
    profile = await service.get_next_profile(telegram_id)
    return profile


@router.post("/swipe", response_model=SwipeResponse)
async def swipe_profile(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    swipe_data: SwipeRequest = ...,
    db: AsyncSession = Depends(get_db),
):
    """Отправить свайп (лайк/пропуск) анкете."""
    service = ProfileService(db)

    # Находим профиль пользователя
    user_profile = await service.get_profile_by_telegram_id(telegram_id)
    if not user_profile:
        raise HTTPException(status_code=404, detail="Профиль не найден. Создайте анкету.")

    result = await service.record_swipe(
        swiper_id=user_profile.id,
        swiped_id=swipe_data.profile_id,
        action=swipe_data.action,
    )
    await db.commit()

    return SwipeResponse(**result)


@router.get("/matches", response_model=List[MatchResponse])
async def get_matches(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """Получить список мэтчей пользователя."""
    service = ProfileService(db)
    matches = await service.get_matches(telegram_id)
    return matches
