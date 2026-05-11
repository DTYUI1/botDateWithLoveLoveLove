"""
Сервис для работы с профилями пользователей.
"""

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.user import User
from models.profile import Profile
from models.photo import Photo as PhotoModel
from schemas.profile import ProfileCreate, ProfileUpdate, ProfileResponse, ProfileShort
from loguru import logger


def calculate_age(birth_date: date) -> int:
    """Вычисляет возраст по дате рождения."""
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def calculate_completion_pct(profile: Profile) -> int:
    """Вычисляет процент заполнения профиля."""
    fields = [
        profile.display_name,
        profile.date_of_birth,
        profile.gender,
        profile.bio,
        profile.city,
        profile.looking_for,
        profile.interests,
    ]
    filled = sum(1 for f in fields if f and (not isinstance(f, list) or len(f) > 0))
    return int((filled / len(fields)) * 100)


class ProfileService:
    """Сервис для CRUD операций с профилями."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_primary_photo_url(self, profile_id) -> Optional[str]:
        """Получить относительный путь /api/v1/profile/photo/{id}/raw для основного фото.

        Бот сам достанет байты у backend (которому MinIO доступен по docker-имени),
        и отправит их в Telegram через BufferedInputFile — поэтому presigned URL
        не нужен (Telegram не достучится до minio:9000).
        """
        try:
            result = await self.db.execute(
                select(PhotoModel).where(
                    and_(
                        PhotoModel.profile_id == profile_id,
                        PhotoModel.is_primary.is_(True),
                        PhotoModel.deleted_at.is_(None),
                    )
                ).limit(1)
            )
            photo = result.scalar_one_or_none()
            if not photo:
                result = await self.db.execute(
                    select(PhotoModel).where(
                        and_(
                            PhotoModel.profile_id == profile_id,
                            PhotoModel.deleted_at.is_(None),
                        )
                    ).order_by(PhotoModel.sort_order).limit(1)
                )
                photo = result.scalar_one_or_none()
            if not photo:
                return None
            return f"/api/v1/profile/photo/{photo.id}/raw"
        except Exception as e:
            logger.warning(f"[ProfileService] Не удалось получить primary photo: {e}")
            return None

    async def _get_username_by_profile_id(self, profile_id) -> Optional[str]:
        """Получить telegram username владельца профиля."""
        result = await self.db.execute(
            select(User.username)
            .join(Profile, Profile.user_id == User.id)
            .where(Profile.id == profile_id)
        )
        row = result.first()
        return row[0] if row else None

    # ============================================
    # User
    # ============================================

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> User:
        """Получает или создаёт пользователя по Telegram ID."""
        result = await self.db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user:
            # Обновляем данные
            if username and user.username != username:
                user.username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            user.last_active_at = datetime.utcnow()
            return user

        # Создаём нового пользователя
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name or f"user_{telegram_id}",
            last_name=last_name,
            language_code=language_code or "ru",
        )
        self.db.add(user)
        await self.db.flush()
        return user

    # ============================================
    # Profile
    # ============================================

    async def get_profile_by_telegram_id(self, telegram_id: int) -> Optional[ProfileResponse]:
        """Получает профиль по Telegram ID пользователя."""
        result = await self.db.execute(
            select(Profile)
            .join(User, Profile.user_id == User.id)
            .where(User.telegram_id == telegram_id)
            .options(selectinload(Profile.user))
        )
        profile = result.scalar_one_or_none()

        if not profile:
            return None

        return self._to_response(profile)

    async def create_profile(
        self,
        telegram_id: int,
        profile_data: ProfileCreate,
    ) -> ProfileResponse:
        """Создаёт профиль пользователя."""
        # Находим пользователя
        result = await self.db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError(f"Пользователь с telegram_id={telegram_id} не найден")

        # Проверяем, нет ли уже профиля
        existing = await self.db.execute(
            select(Profile).where(Profile.user_id == user.id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Профиль уже существует")

        # Вычисляем возраст и создаём профиль
        age = profile_data.age
        dob = None
        if age:
            # Приблизительная дата рождения
            today = date.today()
            dob = today.replace(year=today.year - age)

        profile = Profile(
            user_id=user.id,
            display_name=profile_data.display_name,
            date_of_birth=dob,
            gender=profile_data.gender,
            bio=profile_data.bio,
            interests=profile_data.interests or [],
            city=profile_data.city,
            looking_for=profile_data.looking_for,
        )
        profile.profile_completion_pct = calculate_completion_pct(profile)

        self.db.add(profile)
        await self.db.flush()

        return self._to_response(profile)

    async def update_profile(
        self,
        telegram_id: int,
        profile_data: ProfileUpdate,
    ) -> Optional[ProfileResponse]:
        """Обновляет профиль пользователя."""
        result = await self.db.execute(
            select(Profile)
            .join(User, Profile.user_id == User.id)
            .where(User.telegram_id == telegram_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            return None

        # Обновляем поля
        update_data = profile_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(profile, field, value)

        profile.profile_completion_pct = calculate_completion_pct(profile)
        profile.updated_at = datetime.utcnow()

        await self.db.flush()
        return self._to_response(profile)

    # ============================================
    # Matching helpers
    # ============================================

    async def get_next_profile(self, telegram_id: int) -> Optional[ProfileShort]:
        """Получает следующую анкету для свайпа."""
        from models.swipe import Swipe as SwipeModel

        # Находим профиль текущего пользователя
        user_result = await self.db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return None

        my_profile_result = await self.db.execute(
            select(Profile).where(Profile.user_id == user.id)
        )
        my_profile = my_profile_result.scalar_one_or_none()
        if not my_profile:
            return None

        # Получаем ID тех, кого уже свайпали
        swiped_result = await self.db.execute(
            select(SwipeModel.swiped_id).where(SwipeModel.swiper_id == my_profile.id)
        )
        swiped_ids = {row[0] for row in swiped_result.all()}

        # Фильтруем уже свайпнутые профили + предпочтения по полу + наличие фото
        profiles_with_photo = (
            select(PhotoModel.profile_id)
            .where(PhotoModel.deleted_at.is_(None))
        ).scalar_subquery()

        filters = [
            Profile.id != my_profile.id,
            Profile.is_active.is_(True),
            Profile.id.in_(profiles_with_photo),
        ]
        if swiped_ids:
            filters.append(Profile.id.notin_(swiped_ids))
        if my_profile.looking_for and my_profile.looking_for != "both":
            filters.append(Profile.gender == my_profile.looking_for)
        if my_profile.city:
            filters.append(Profile.city == my_profile.city)
        query = select(Profile).where(and_(*filters)).limit(1)

        result = await self.db.execute(query)
        profile = result.scalar_one_or_none()

        if not profile:
            return None

        age = calculate_age(profile.date_of_birth) if profile.date_of_birth else None

        primary_photo_url = await self._get_primary_photo_url(profile.id)
        username = await self._get_username_by_profile_id(profile.id)

        return ProfileShort(
            id=profile.id,
            display_name=profile.display_name,
            age=age,
            city=profile.city,
            bio=profile.bio,
            interests=profile.interests or [],
            primary_photo_url=primary_photo_url,
            username=username,
        )

    async def record_swipe(
        self,
        swiper_id: UUID,
        swiped_id: UUID,
        action: str,
    ) -> dict:
        """Записывает свайп и проверяет мэтч."""
        from models.swipe import Swipe
        from models.match import Match

        swipe = Swipe(
            swiper_id=swiper_id,
            swiped_id=swiped_id,
            action=action,
        )
        self.db.add(swipe)

        is_match = False
        match = None
        match_profile_name = None
        match_username = None

        # Если лайк — проверяем взаимность
        if action == "like":
            mutual_result = await self.db.execute(
                select(Swipe).where(
                    and_(
                        Swipe.swiper_id == swiped_id,
                        Swipe.swiped_id == swiper_id,
                        Swipe.action == "like",
                    )
                )
            )
            mutual = mutual_result.scalar_one_or_none()

            if mutual:
                # Мэтч!
                match = Match(
                    profile1_id=min(swiper_id, swiped_id),
                    profile2_id=max(swiper_id, swiped_id),
                    initiator_id=swiper_id,
                )
                self.db.add(match)
                is_match = True

                # Получаем имя и username партнёра для уведомления
                partner_result = await self.db.execute(
                    select(Profile, User)
                    .join(User, Profile.user_id == User.id)
                    .where(Profile.id == swiped_id)
                )
                row = partner_result.first()
                if row:
                    swiped_profile, swiped_user = row
                    match_profile_name = swiped_profile.display_name
                    match_username = swiped_user.username

        await self.db.flush()

        return {
            "is_match": is_match,
            "swipe_id": swipe.id,
            "match_id": match.id if match else None,
            "match_profile_name": match_profile_name,
            "match_username": match_username,
        }

    async def get_matches(self, telegram_id: int) -> List[dict]:
        """Получает список мэтчей пользователя."""
        from models.match import Match

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

        result = await self.db.execute(
            select(Match)
            .where(
                and_(
                    Match.status == "active",
                    (Match.profile1_id == my_profile.id) | (Match.profile2_id == my_profile.id),
                )
            )
            .order_by(Match.updated_at.desc())
        )
        matches = result.scalars().all()

        # Для каждого мэтча находим профиль партнёра
        result_list = []
        for match in matches:
            partner_id = match.profile2_id if match.profile1_id == my_profile.id else match.profile1_id
            partner_result = await self.db.execute(
                select(Profile, User)
                .join(User, Profile.user_id == User.id)
                .where(Profile.id == partner_id)
            )
            row = partner_result.first()

            if row:
                partner, partner_user = row
                age = calculate_age(partner.date_of_birth) if partner.date_of_birth else None
                primary_photo_url = await self._get_primary_photo_url(partner.id)
                result_list.append({
                    "id": match.id,
                    "profile": ProfileShort(
                        id=partner.id,
                        display_name=partner.display_name,
                        age=age,
                        city=partner.city,
                        bio=partner.bio,
                        interests=partner.interests or [],
                        primary_photo_url=primary_photo_url,
                        username=partner_user.username,
                    ),
                    "message_count": match.message_count,
                    "last_message_at": match.last_message_at,
                    "created_at": match.created_at,
                })

        return result_list

    # ============================================
    # Helpers
    # ============================================

    def _to_response(self, profile: Profile) -> ProfileResponse:
        """Преобразует модель Profile в Response схему."""
        age = calculate_age(profile.date_of_birth) if profile.date_of_birth else None
        return ProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            display_name=profile.display_name,
            age=age,
            gender=profile.gender,
            bio=profile.bio,
            interests=profile.interests if profile.interests else [],
            city=profile.city,
            looking_for=profile.looking_for,
            is_active=profile.is_active,
            is_verified=profile.is_verified,
            profile_completion_pct=profile.profile_completion_pct,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
