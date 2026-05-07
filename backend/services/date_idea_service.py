"""
Сервис подбора идей для свиданий.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.date_idea import DateIdea
from models.match import Match
from models.profile import Profile
from models.user import User
from schemas.date_idea import DateIdeaCreate


class DateIdeaService:
    """Бизнес-логика каталога идей для свиданий."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile_by_telegram_id(self, telegram_id: int) -> Optional[Profile]:
        result = await self.db.execute(
            select(Profile)
            .join(User, Profile.user_id == User.id)
            .where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create_idea(self, data: DateIdeaCreate) -> DateIdea:
        idea = DateIdea(**data.model_dump())
        self.db.add(idea)
        await self.db.flush()
        await self.db.refresh(idea)
        return idea

    async def list_ideas(
        self,
        city: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> list[DateIdea]:
        query = select(DateIdea).where(DateIdea.is_active == True)
        if city:
            query = query.where(or_(DateIdea.city == city, DateIdea.city.is_(None)))
        if category:
            query = query.where(DateIdea.category == category)

        result = await self.db.execute(
            query.order_by(
                DateIdea.positive_feedback_count.desc(),
                DateIdea.suggested_count.asc(),
                DateIdea.created_at.desc(),
            ).limit(limit)
        )
        return result.scalars().all()

    async def suggest_for_user(
        self,
        telegram_id: int,
        match_id: Optional[UUID] = None,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> list[DateIdea]:
        profile = await self.get_profile_by_telegram_id(telegram_id)
        if not profile:
            raise ValueError("Профиль не найден")

        interests = set(profile.interests or [])
        city = profile.city

        if match_id:
            match_result = await self.db.execute(
                select(Match).where(
                    Match.id == match_id,
                    Match.status == "active",
                    or_(Match.profile1_id == profile.id, Match.profile2_id == profile.id),
                )
            )
            match = match_result.scalar_one_or_none()
            if not match:
                raise ValueError("Мэтч не найден")

            partner_id = match.profile2_id if match.profile1_id == profile.id else match.profile1_id
            partner_result = await self.db.execute(select(Profile).where(Profile.id == partner_id))
            partner = partner_result.scalar_one_or_none()
            if partner:
                interests.update(partner.interests or [])
                city = city or partner.city

        candidates = await self.list_ideas(city=city, category=category, limit=100)

        def score(idea: DateIdea) -> tuple[int, int, int]:
            idea_interests = set(idea.suitable_interests or [])
            city_score = 1 if city and idea.city == city else 0
            interest_score = len(interests & idea_interests) if idea_interests else 0
            feedback_score = idea.positive_feedback_count or 0
            return city_score, interest_score, feedback_score

        suggestions = sorted(candidates, key=score, reverse=True)[:limit]
        for idea in suggestions:
            idea.suggested_count = (idea.suggested_count or 0) + 1

        await self.db.flush()
        return suggestions

    async def add_feedback(self, idea_id: UUID, positive: bool) -> Optional[DateIdea]:
        result = await self.db.execute(
            select(DateIdea).where(DateIdea.id == idea_id, DateIdea.is_active == True)
        )
        idea = result.scalar_one_or_none()
        if not idea:
            return None

        if positive:
            idea.positive_feedback_count = (idea.positive_feedback_count or 0) + 1

        await self.db.flush()
        await self.db.refresh(idea)
        return idea
