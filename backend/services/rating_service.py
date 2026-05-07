"""
Сервис расчёта рейтингов пользователей.

Реализует 3 уровня алгоритмов:
1. Уровень 1: Первичный рейтинг (заполненность профиля, фото, верификация)
2. Уровень 2: Поведенческий рейтинг (лайки, мэтчи, активность)
3. Уровень 3: Комбинированный рейтинг (взвешенная сумма всех факторов)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.profile import Profile
from models.photo import Photo as PhotoModel
from models.rating import RatingCombined as RatingCombinedModel
from infrastructure.redis.cache_patterns import RatingCache


# ============================================
# КОНСТАНТЫ И ВЕСА
# ============================================

# Веса для комбинированного рейтинга
PRIMARY_WEIGHT = 0.40
BEHAVIORAL_WEIGHT = 0.50
REFERRAL_WEIGHT = 0.10

# Бонусы
VERIFICATION_BONUS = 0.05  # +5% за верификацию

# Tier'ы рейтинга
TIERS = {
    "S": 0.90,  # Топ 10%
    "A": 0.75,  # Топ 25%
    "B": 0.60,  # Топ 40%
    "C": 0.45,  # Средний
    "D": 0.30,  # Ниже среднего
    "E": 0.00,  # Новый/незаполненный
}


# ============================================
# УРОВЕНЬ 1: Первичный рейтинг
# ============================================

class PrimaryRatingCalculator:
    """
    Расчёт первичного рейтинга на основе данных анкеты.
    
    Факторы:
    - Заполненность профиля (0-1)
    - Количество и качество фото (0-1)
    - Верификация (boolean bonus)
    - Соответствие предпочтениям (0-1)
    """

    @staticmethod
    def calculate_completeness_score(profile: Profile) -> float:
        """
        Вычислить score заполненности профиля.
        
        Fields:
        - display_name
        - date_of_birth
        - gender
        - bio
        - city
        - looking_for
        - interests
        - height_cm
        - age_range_min/max
        - distance_max_km
        """
        fields = {
            "display_name": bool(profile.display_name),
            "date_of_birth": bool(profile.date_of_birth),
            "gender": bool(profile.gender),
            "bio": bool(profile.bio) and len(profile.bio) > 20,
            "city": bool(profile.city),
            "looking_for": bool(profile.looking_for),
            "interests": bool(profile.interests) and len(profile.interests) > 0,
            "height_cm": bool(profile.height_cm),
            "age_range": bool(profile.age_range_min and profile.age_range_max),
            "distance_max": bool(profile.distance_max_km),
        }

        weights = {
            "display_name": 0.05,
            "date_of_birth": 0.10,
            "gender": 0.10,
            "bio": 0.25,
            "city": 0.15,
            "looking_for": 0.10,
            "interests": 0.15,
            "height_cm": 0.05,
            "age_range": 0.03,
            "distance_max": 0.02,
        }

        score = sum(weights[field] * (1 if value else 0) for field, value in fields.items())
        return round(min(score, 1.0), 4)

    @staticmethod
    def calculate_photo_score(photo_count: int, has_primary: bool) -> float:
        """
        Вычислить score фото.
        
        Args:
            photo_count: Количество фото
            has_primary: Есть ли главное фото
        """
        if photo_count == 0:
            return 0.0

        # Базовый score от количества (логарифмическая шкала)
        import math
        count_score = min(math.log(photo_count + 1) / math.log(5), 1.0)  # 4+ фото = 1.0

        # Бонус за главное фото
        primary_bonus = 0.2 if has_primary else 0.0

        score = count_score * 0.7 + primary_bonus * 0.3
        return round(min(score, 1.0), 4)

    @staticmethod
    def calculate_verification_bonus(is_verified: bool) -> float:
        """Бонус за верификацию."""
        return VERIFICATION_BONUS if is_verified else 0.0

    @classmethod
    def calculate_total(
        cls,
        profile: Profile,
        photo_count: int,
        has_primary_photo: bool
    ) -> Dict[str, float]:
        """
        Рассчитать полный первичный рейтинг.
        
        Returns:
            Dict с scores и total
        """
        completeness = cls.calculate_completeness_score(profile)
        photo_score = cls.calculate_photo_score(photo_count, has_primary_photo)
        verification_bonus = cls.calculate_verification_bonus(profile.is_verified)

        # Weighted sum (completeness 60%, photo 40%) + verification bonus
        total = (completeness * 0.6 + photo_score * 0.4) + verification_bonus
        total = min(total, 1.0)

        return {
            "completeness_score": completeness,
            "photo_score": photo_score,
            "verification_bonus": verification_bonus,
            "total_score": round(total, 4),
        }


# ============================================
# УРОВЕНЬ 2: Поведенческий рейтинг
# ============================================

class BehavioralRatingCalculator:
    """
    Расчёт поведенческого рейтинга на основе активности пользователя.
    
    Факторы:
    - Количество полученных лайков
    - Соотношение лайков/пропусков
    - Частота мэтчей
    - Инициация диалогов
    - Паттерны активности
    """

    @staticmethod
    def calculate_like_count_score(like_count: int) -> float:
        """
        Score на основе количества полученных лайков.
        Логарифмическая шкала: 100+ лайков = 1.0
        """
        import math
        if like_count == 0:
            return 0.0
        score = math.log(like_count + 1) / math.log(101)
        return round(min(score, 1.0), 4)

    @staticmethod
    def calculate_like_pass_ratio_score(likes_received: int, passes_received: int) -> float:
        """
        Score соотношения лайков/пропусков.
        >80% лайков = 1.0, <20% = 0.0
        """
        total = likes_received + passes_received
        if total == 0:
            return 0.5  # Нейтрально для новых пользователей

        ratio = likes_received / total
        # Нормализация: 0.2 -> 0.0, 0.8 -> 1.0
        score = (ratio - 0.2) / 0.6
        return round(max(min(score, 1.0), 0.0), 4)

    @staticmethod
    def calculate_match_rate_score(matches: int, swipes: int) -> float:
        """
        Score частоты мэтчей.
        >20% мэтчей = 1.0
        """
        if swipes == 0:
            return 0.0

        match_rate = matches / swipes
        # Нормализация: 0% -> 0.0, 20% -> 1.0
        score = match_rate / 0.20
        return round(min(score, 1.0), 4)

    @staticmethod
    def calculate_conversation_initiation_score(
        messages_sent: int,
        matches_count: int
    ) -> float:
        """
        Score инициации диалогов.
        Пишет в 50%+ мэтчей = 1.0
        """
        if matches_count == 0:
            return 0.5  # Нейтрально

        # Предполагаем, что 1 сообщение = 1 диалог
        initiation_rate = min(messages_sent / matches_count, 1.0)
        # Нормализация: 0% -> 0.0, 50% -> 1.0
        score = initiation_rate / 0.5
        return round(min(score, 1.0), 4)

    @staticmethod
    def calculate_activity_pattern_score(
        days_active: int,
        last_active_days_ago: int
    ) -> float:
        """
        Score паттернов активности.
        Активен последние 7 дней и 30+ дней всего = 1.0
        """
        if days_active == 0:
            return 0.0

        # Longevity score (сколько дней всего активен)
        longevity = min(days_active / 30, 1.0) * 0.6

        # Recency score (как недавно был активен)
        if last_active_days_ago == 0:
            recency = 1.0
        elif last_active_days_ago <= 7:
            recency = 0.7
        elif last_active_days_ago <= 30:
            recency = 0.4
        else:
            recency = 0.1
        recency *= 0.4

        return round(longevity + recency, 4)

    @classmethod
    def calculate_total(
        cls,
        like_received_count: int,
        pass_received_count: int,
        matches_count: int,
        total_swipes: int,
        messages_sent: int,
        days_active: int,
        last_active_days_ago: int
    ) -> Dict[str, float]:
        """
        Рассчитать полный поведенческий рейтинг.
        
        Returns:
            Dict с scores и total
        """
        like_count_score = cls.calculate_like_count_score(like_received_count)
        like_pass_ratio = cls.calculate_like_pass_ratio_score(
            like_received_count, pass_received_count
        )
        match_rate = cls.calculate_match_rate_score(matches_count, total_swipes)
        conversation_score = cls.calculate_conversation_initiation_score(
            messages_sent, matches_count
        )
        activity_score = cls.calculate_activity_pattern_score(
            days_active, last_active_days_ago
        )

        # Weighted sum
        weights = {
            "like_count": 0.20,
            "like_pass_ratio": 0.20,
            "match_rate": 0.25,
            "conversation": 0.15,
            "activity": 0.20,
        }

        scores = {
            "like_count_score": like_count_score,
            "like_pass_ratio_score": like_pass_ratio,
            "match_rate_score": match_rate,
            "conversation_initiation_score": conversation_score,
            "activity_pattern_score": activity_score,
        }

        total = (
            weights["like_count"] * like_count_score +
            weights["like_pass_ratio"] * like_pass_ratio +
            weights["match_rate"] * match_rate +
            weights["conversation"] * conversation_score +
            weights["activity"] * activity_score
        )

        scores["total_score"] = round(min(total, 1.0), 4)
        return scores


# ============================================
# УРОВЕНЬ 3: Комбинированный рейтинг
# ============================================

class CombinedRatingCalculator:
    """
    Расчёт комбинированного рейтинга.
    
    Формула:
    total = primary * 0.40 + behavioral * 0.50 + referral_bonus * 0.10
    """

    @staticmethod
    def calculate_total(
        primary_score: float,
        behavioral_score: float,
        referral_bonus: float = 0.0,
        primary_weight: float = PRIMARY_WEIGHT,
        behavioral_weight: float = BEHAVIORAL_WEIGHT,
        referral_weight: float = REFERRAL_WEIGHT
    ) -> Dict[str, Any]:
        """
        Рассчитать комбинированный рейтинг.
        
        Returns:
            Dict с scores, total, tier, percentile
        """
        total = (
            primary_score * primary_weight +
            behavioral_score * behavioral_weight +
            referral_bonus * referral_weight
        )
        total = min(total, 1.0)

        # Определить tier
        tier = CombinedRatingCalculator._assign_tier(total)

        return {
            "primary_score": round(primary_score, 4),
            "primary_weight": primary_weight,
            "behavioral_score": round(behavioral_score, 4),
            "behavioral_weight": behavioral_weight,
            "referral_bonus": round(referral_bonus, 4),
            "referral_weight": referral_weight,
            "total_score": round(total, 4),
            "tier": tier,
        }

    @staticmethod
    def _assign_tier(total_score: float) -> str:
        """Присвоить tier на основе score."""
        for tier_name, threshold in TIERS.items():
            if total_score >= threshold:
                return tier_name
        return "E"

    @staticmethod
    def calculate_percentile(
        user_score: float,
        all_scores: List[float]
    ) -> float:
        """
        Вычислить перцентиль пользователя.
        
        Args:
            user_score: Score пользователя
            all_scores: Список всех scores
        """
        if not all_scores:
            return 0.0

        below_count = sum(1 for score in all_scores if score < user_score)
        percentile = below_count / len(all_scores)
        return round(percentile, 4)


# ============================================
# MAIN SERVICE
# ============================================

class RatingService:
    """
    Главный сервис для расчёта всех уровней рейтинга.
    
    Usage:
        service = RatingService(db_session, rating_cache)
        result = await service.calculate_all_ratings(profile_id)
    """

    def __init__(self, db: AsyncSession, rating_cache: Optional[RatingCache] = None):
        self.db = db
        self.rating_cache = rating_cache

    async def calculate_primary_rating(
        self,
        profile: Profile
    ) -> Dict[str, float]:
        """Уровень 1: Расчёт первичного рейтинга."""
        # Получить количество фото
        photo_result = await self.db.execute(
            select(func.count(PhotoModel.id)).where(
                and_(
                    PhotoModel.profile_id == profile.id,
                    PhotoModel.deleted_at.is_(None)
                )
            )
        )
        photo_count = photo_result.scalar() or 0

        # Проверить наличие главного фото
        primary_result = await self.db.execute(
            select(func.count(PhotoModel.id)).where(
                and_(
                    PhotoModel.profile_id == profile.id,
                    PhotoModel.is_primary == True,
                    PhotoModel.deleted_at.is_(None)
                )
            )
        )
        has_primary_photo = (primary_result.scalar() or 0) > 0

        # Рассчитать
        return PrimaryRatingCalculator.calculate_total(
            profile, photo_count, has_primary_photo
        )

    async def calculate_behavioral_rating(
        self,
        profile: Profile,
        like_received_count: int = 0,
        pass_received_count: int = 0,
        matches_count: int = 0,
        total_swipes: int = 0,
        messages_sent: int = 0,
        days_active: int = 0,
        last_active_days_ago: int = 0
    ) -> Dict[str, float]:
        """Уровень 2: Расчёт поведенческого рейтинга."""
        return BehavioralRatingCalculator.calculate_total(
            like_received_count=like_received_count,
            pass_received_count=pass_received_count,
            matches_count=matches_count,
            total_swipes=total_swipes,
            messages_sent=messages_sent,
            days_active=days_active,
            last_active_days_ago=last_active_days_ago
        )

    async def calculate_combined_rating(
        self,
        primary_score: float,
        behavioral_score: float,
        referral_bonus: float = 0.0
    ) -> Dict[str, Any]:
        """Уровень 3: Расчёт комбинированного рейтинга."""
        return CombinedRatingCalculator.calculate_total(
            primary_score, behavioral_score, referral_bonus
        )

    async def calculate_all_ratings(
        self,
        profile: Profile,
        behavioral_stats: Dict[str, int] = None
    ) -> Dict[str, Any]:
        """
        Рассчитать все уровни рейтинга и сохранить в БД.
        
        Args:
            profile: Профиль пользователя
            behavioral_stats: Статистика поведения (опционально)
            
        Returns:
            Dict со всеми scores и rating объектом
        """
        # Уровень 1
        primary_result = await self.calculate_primary_rating(profile)

        # Уровень 2
        behavioral_stats = behavioral_stats or {}
        behavioral_result = await self.calculate_behavioral_rating(
            profile, **behavioral_stats
        )

        # Уровень 3
        combined_result = await self.calculate_combined_rating(
            primary_result["total_score"],
            behavioral_result["total_score"],
            behavioral_stats.get("referral_bonus", 0.0)
        )

        # Обновить кэш
        if self.rating_cache:
            await self.rating_cache.update_rating(
                "combined",
                profile.id,
                combined_result["total_score"]
            )

        return {
            "primary": primary_result,
            "behavioral": behavioral_result,
            "combined": combined_result,
        }

    async def save_rating_to_db(
        self,
        profile_id,
        combined_result: Dict[str, Any]
    ) -> RatingCombinedModel:
        """Сохранить комбинированный рейтинг в БД."""
        from core.database import async_session_factory

        async with async_session_factory() as session:
            rating = await self.upsert_rating_in_session(profile_id, combined_result, session=session)
            await session.commit()
            await session.refresh(rating)
            return rating

    async def upsert_rating_in_session(
        self,
        profile_id,
        combined_result: Dict[str, Any],
        session: Optional[AsyncSession] = None,
    ) -> RatingCombinedModel:
        """Создать или обновить комбинированный рейтинг в указанной сессии."""
        session = session or self.db
        result = await session.execute(
            select(RatingCombinedModel).where(
                RatingCombinedModel.profile_id == profile_id
            )
        )
        rating = result.scalar_one_or_none()

        values = {
            "primary_score": combined_result["primary_score"],
            "primary_weight": combined_result["primary_weight"],
            "behavioral_score": combined_result["behavioral_score"],
            "behavioral_weight": combined_result["behavioral_weight"],
            "referral_bonus": combined_result["referral_bonus"],
            "referral_weight": combined_result["referral_weight"],
            "total_score": combined_result["total_score"],
            "tier": combined_result["tier"],
            "calculated_at": datetime.utcnow(),
        }

        if rating:
            for field, value in values.items():
                setattr(rating, field, value)
        else:
            rating = RatingCombinedModel(profile_id=profile_id, **values)
            session.add(rating)

        await session.flush()
        return rating
