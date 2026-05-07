"""
API роутер для чата между мэтчами.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from schemas.message import MessageCreate, MessageListResponse, MessageResponse
from services.message_service import MessageService

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/{match_id}", response_model=MessageListResponse)
async def get_messages(
    match_id: UUID,
    telegram_id: Annotated[int, Query(description="Telegram ID пользователя")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
):
    """Получить историю сообщений активного мэтча."""
    logger.info(f"[Backend Messages] GET /messages/{match_id} telegram_id={telegram_id}")

    service = MessageService(db)
    profile = await service.get_profile_by_telegram_id(telegram_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    try:
        messages, total = await service.list_messages(
            match_id=match_id,
            profile_id=profile.id,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return MessageListResponse(
        messages=[MessageResponse.model_validate(message) for message in messages],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.post("/{match_id}", response_model=MessageResponse)
async def send_message(
    match_id: UUID,
    message_data: MessageCreate,
    telegram_id: Annotated[int, Query(description="Telegram ID пользователя")],
    db: AsyncSession = Depends(get_db),
):
    """Отправить сообщение в активный мэтч."""
    logger.info(f"[Backend Messages] POST /messages/{match_id} telegram_id={telegram_id}")

    service = MessageService(db)
    profile = await service.get_profile_by_telegram_id(telegram_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    try:
        message = await service.send_message(
            match_id=match_id,
            sender_profile_id=profile.id,
            data=message_data,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Backend Messages] ОШИБКА send_message: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось отправить сообщение")

    return MessageResponse.model_validate(message)
