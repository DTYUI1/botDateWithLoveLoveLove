"""
API роутер для идей свиданий.
"""

from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from schemas.date_idea import DateIdeaCreate, DateIdeaFeedback, DateIdeaResponse
from services.date_idea_service import DateIdeaService

router = APIRouter(prefix="/date_ideas", tags=["date_ideas"])


@router.get("", response_model=List[DateIdeaResponse])
async def list_date_ideas(
    city: Optional[str] = Query(None, description="Город"),
    category: Optional[str] = Query(
        None,
        pattern="^(cafe|activity|outdoor|cultural|entertainment)$",
        description="Категория идеи",
    ),
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: AsyncSession = Depends(get_db),
):
    """Получить каталог активных идей свиданий."""
    service = DateIdeaService(db)
    ideas = await service.list_ideas(city=city, category=category, limit=limit)
    return [DateIdeaResponse.model_validate(idea) for idea in ideas]


@router.post("", response_model=DateIdeaResponse)
async def create_date_idea(
    idea_data: DateIdeaCreate,
    db: AsyncSession = Depends(get_db),
):
    """Создать идею свидания для каталога."""
    service = DateIdeaService(db)
    idea = await service.create_idea(idea_data)
    await db.commit()
    return DateIdeaResponse.model_validate(idea)


@router.get("/suggest", response_model=List[DateIdeaResponse])
async def suggest_date_ideas(
    telegram_id: Annotated[int, Query(description="Telegram ID пользователя")],
    match_id: Optional[UUID] = Query(None, description="ID мэтча для совместных интересов"),
    category: Optional[str] = Query(
        None,
        pattern="^(cafe|activity|outdoor|cultural|entertainment)$",
        description="Категория идеи",
    ),
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
    db: AsyncSession = Depends(get_db),
):
    """Подобрать идеи с учётом города и интересов пользователя/мэтча."""
    logger.info(f"[Backend DateIdeas] GET /date_ideas/suggest telegram_id={telegram_id}")

    service = DateIdeaService(db)
    try:
        ideas = await service.suggest_for_user(
            telegram_id=telegram_id,
            match_id=match_id,
            category=category,
            limit=limit,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[Backend DateIdeas] ОШИБКА suggest: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось подобрать идеи")

    return [DateIdeaResponse.model_validate(idea) for idea in ideas]


@router.post("/{idea_id}/feedback", response_model=DateIdeaResponse)
async def add_date_idea_feedback(
    idea_id: UUID,
    feedback: DateIdeaFeedback,
    db: AsyncSession = Depends(get_db),
):
    """Сохранить обратную связь по идее свидания."""
    service = DateIdeaService(db)
    idea = await service.add_feedback(idea_id, feedback.positive)
    if not idea:
        raise HTTPException(status_code=404, detail="Идея не найдена")

    await db.commit()
    return DateIdeaResponse.model_validate(idea)
