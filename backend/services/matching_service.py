"""
Сервис подбора анкет с учётом рейтинга и предпочтений.

Реализует:
- Подбор 10 анкет для свайп-сессии
- Ранжирование по комбинированному рейтингу
- Фильтрацию по предпочтениям (город, возраст, расстояние)
- Кэширование результатов в Redis
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import date

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.profile import Profile
from models.user import User
from models.photo import Photo as PhotoModel
from models.swipe import Swipe as SwipeModel
from models.rating import RatingCombined as RatingCombinedModel
from infrastructure.redis.cache_patterns import ProfileSessionCache


class MatchingService:
    """
    Сервис для подбора анкет.
    
    Алгоритм:
    1. Получить профиль пользователя
    2. Получить уже свайпнутые анкеты
    3. Отфильтровать по предпочтениям
    4. Отранжировать по рейтингу
    5. Закэшировать 10 анкет в Redis
    """

    PROFILES_PER_SESSION = 10
    CACHE_TTL = 3600  # 1 час

    def __init__(
        self,
        db: AsyncSession,
        session_cache: Optional[ProfileSessionCache] = None
    ):
        self.db = db
        self.session_cache = session_cache

    async def get_or_create_matching_session(
        self,
        telegram_id: int
    ) -> str:
        """
        Получить или создать ID сессии для подбора.
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            session_id
        """
        # В реальном приложении можно сохранять сессии в БД
        # Для простоты генерируем новый UUID
        return str(uuid.uuid4())

    async def get_matching_profiles(
        self,
        telegram_id: int,
        limit: int = PROFILES_PER_SESSION
    ) -> List[Dict[str, Any]]:
        """
        Получить анкеты для свайп-сессии.
        
        Args:
            telegram_id: Telegram ID пользователя
            limit: Количество анкет (по умолчанию 10)
            
        Returns:
            Список анкет с рейтингами
        """
        # 1. Получить профиль текущего пользователя
        user_result = await self.db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return []

        my_profile_result = await self.db.execute(
            select(Profile).where(Profile.user_id == user.id)
        )
        my_profile = my_profile_result.scalar_one_or_none()
        if not my_profile:
            return []

        # 2. Получить уже свайпнутые анкеты
        swiped_result = await self.db.execute(
            select(SwipeModel.swiped_id).where(SwipeModel.swiper_id == my_profile.id)
        )
        swiped_ids = {row[0] for row in swiped_result.all()}

        # 3. Построить запрос с фильтрами
        # Подзапрос: id профилей, у которых есть хотя бы одно неудалённое фото
        profiles_with_photo = (
            select(PhotoModel.profile_id)
            .where(PhotoModel.deleted_at.is_(None))
        ).scalar_subquery()

        def _build_query(include_city: bool):
            base = (
                select(
                    Profile,
                    RatingCombinedModel.total_score.label('rating_score')
                )
                .outerjoin(
                    RatingCombinedModel,
                    Profile.id == RatingCombinedModel.profile_id
                )
                .where(
                    and_(
                        Profile.id != my_profile.id,
                        Profile.is_active.is_(True),
                        Profile.id.notin_(swiped_ids) if swiped_ids else True,
                        Profile.id.in_(profiles_with_photo),
                    )
                )
            )
            base = self._apply_preferences_filters(base, my_profile, include_city=include_city)
            base = base.order_by(RatingCombinedModel.total_score.desc().nullslast())
            return base.limit(limit)

        # 4–6. Сначала пробуем строгий поиск (по городу пользователя)
        result = await self.db.execute(_build_query(include_city=True))
        rows = result.all()

        # 4b. Soft fallback: если в городе никого нет — расширяем поиск
        if not rows and my_profile.city:
            logger.info(
                f"[Matching] Город {my_profile.city!r}: 0 кандидатов — "
                "расширяю поиск без city-фильтра"
            )
            result = await self.db.execute(_build_query(include_city=False))
            rows = result.all()

        if not rows:
            return []

        profile_ids = [profile.id for profile, _ in rows]

        # 7a. Подгружаем primary photos одним запросом
        photo_result = await self.db.execute(
            select(PhotoModel).where(
                and_(
                    PhotoModel.profile_id.in_(profile_ids),
                    PhotoModel.deleted_at.is_(None),
                )
            ).order_by(PhotoModel.is_primary.desc(), PhotoModel.sort_order)
        )
        primary_photo_by_profile = {}
        for photo in photo_result.scalars().all():
            primary_photo_by_profile.setdefault(photo.profile_id, photo)

        # 7b. Подгружаем username владельцев профилей
        user_result = await self.db.execute(
            select(Profile.id, User.username)
            .join(User, Profile.user_id == User.id)
            .where(Profile.id.in_(profile_ids))
        )
        username_by_profile = {pid: uname for pid, uname in user_result.all()}

        # 8. Преобразовать в dict
        profiles = []
        for profile, rating_score in rows:
            age = self._calculate_age(profile.date_of_birth) if profile.date_of_birth else None

            primary_photo_url = None
            photo = primary_photo_by_profile.get(profile.id)
            if photo:
                primary_photo_url = f"/api/v1/profile/photo/{photo.id}/raw"

            profiles.append({
                "id": str(profile.id),
                "display_name": profile.display_name,
                "age": age,
                "city": profile.city,
                "bio": profile.bio,
                "interests": profile.interests or [],
                "rating_score": float(rating_score) if rating_score else 0.0,
                "primary_photo_url": primary_photo_url,
                "username": username_by_profile.get(profile.id),
            })

        return profiles

    async def start_matching_session(
        self,
        telegram_id: int,
        session_id: str = None
    ) -> Dict[str, Any]:
        """
        Начать сессию подбора анкет.
        
        Args:
            telegram_id: Telegram ID пользователя
            session_id: ID сессии (опционально)
            
        Returns:
            Dict с session_id, cached_count, profiles
        """
        if not session_id:
            session_id = await self.get_or_create_matching_session(telegram_id)

        # Получить анкеты
        profiles = await self.get_matching_profiles(telegram_id)

        # Закэшировать
        if self.session_cache and profiles:
            await self.session_cache.cache_profiles(
                telegram_id,
                session_id,
                profiles,
                ttl=self.CACHE_TTL
            )

        return {
            "session_id": session_id,
            "cached_count": len(profiles),
            "profiles": profiles[:1],  # Вернуть только первую анкету
        }

    async def get_next_profile_from_cache(
        self,
        telegram_id: int,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получить следующую анкету из кэша.
        
        Args:
            telegram_id: Telegram ID пользователя
            session_id: ID сессии
            
        Returns:
            Анкета или None
        """
        if not self.session_cache:
            return None

        return await self.session_cache.get_next_profile(telegram_id, session_id)

    async def refresh_session(
        self,
        telegram_id: int,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Обновить сессию (новые анкеты).
        
        Args:
            telegram_id: Telegram ID пользователя
            session_id: ID сессии
            
        Returns:
            Dict с session_id, cached_count, profiles
        """
        # Очистить старый кэш
        if self.session_cache:
            await self.session_cache.clear_session(telegram_id, session_id)

        # Начать новую сессию
        return await self.start_matching_session(telegram_id, session_id)

    # ============================================
    # HELPER METHODS
    # ============================================

    def _apply_preferences_filters(
        self,
        query,
        my_profile: Profile,
        *,
        include_city: bool = True,
    ):
        """Применить фильтры по предпочтениям пользователя.

        ``include_city=False`` отключает строгий фильтр по городу — используется
        для soft fallback, когда первый проход не нашёл кандидатов в родном
        городе пользователя.
        """
        filters = []

        # Фильтр по городу (если указан) — отключается на fallback-проходе
        if include_city and my_profile.city:
            filters.append(Profile.city == my_profile.city)

        # Фильтр по полу (looking_for)
        if my_profile.looking_for and my_profile.looking_for != 'both':
            filters.append(Profile.gender == my_profile.looking_for)

        # Фильтр по возрасту (age_range_min/max)
        if my_profile.age_range_min:
            # Вычислить год рождения для максимального возраста
            max_birth_year = date.today().year - my_profile.age_range_min
            filters.append(
                Profile.date_of_birth <= date(max_birth_year + 1, 1, 1)
            )

        if my_profile.age_range_max:
            # Вычислить год рождения для минимального возраста
            min_birth_year = date.today().year - my_profile.age_range_max
            filters.append(
                Profile.date_of_birth >= date(min_birth_year, 1, 1)
            )

        # Применить фильтры
        if filters:
            query = query.where(and_(*filters))

        return query

    @staticmethod
    def _calculate_age(birth_date: date) -> int:
        """Вычислить возраст по дате рождения."""
        today = date.today()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        return age
