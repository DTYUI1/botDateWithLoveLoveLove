"""
API роутер для аутентификации по Telegram ID.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from core.database import get_db
from schemas.user import UserCreate, UserResponse
from services.profile_service import ProfileService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=UserResponse)
async def auth_telegram(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Аутентификация пользователя по Telegram ID.
    Если пользователь не существует — создаёт его.
    """
    logger.info(f"[Backend Auth] POST /auth/telegram telegram_id={user_data.telegram_id}")
    try:
        service = ProfileService(db)
        user = await service.get_or_create_user(
            telegram_id=user_data.telegram_id,
            username=user_data.username,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            language_code=user_data.language_code,
        )
        await db.commit()
        logger.info(f"[Backend Auth] ✅ Пользователь {user_data.telegram_id} создан/получен")
        return user
    except Exception as e:
        logger.error(f"[Backend Auth] ОШИБКА: {type(e).__name__}: {e}")
        raise
