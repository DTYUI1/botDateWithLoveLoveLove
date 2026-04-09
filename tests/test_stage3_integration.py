"""
Интеграционные тесты для Этапа 3.

Покрывает:
- Rating Service (алгоритмы 1-3)
- Matching Service (подбор анкет)
- Redis Cache Patterns (кэширование сессий)
- Photo Service (валидация, CRUD)
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from backend.services.rating_service import (
    PrimaryRatingCalculator,
    BehavioralRatingCalculator,
    CombinedRatingCalculator,
)
from backend.services.photo_service import PhotoService
from infrastructure.redis.cache_patterns import (
    ProfileSessionCache,
    RatingCache,
    SwipeCounterCache,
)


# ============================================
# Rating Service Tests (без реальных моделей)
# ============================================

class TestPrimaryRatingCalculator:
    """Тесты для Уровня 1: Первичный рейтинг."""

    def test_completeness_score_empty_profile(self):
        """Пустой профиль должен иметь 0 score."""
        # Создаём мок профиля без SQLAlchemy
        profile = MagicMock()
        profile.display_name = None
        profile.date_of_birth = None
        profile.gender = None
        profile.bio = None
        profile.city = None
        profile.looking_for = None
        profile.interests = []
        profile.height_cm = None
        profile.age_range_min = None
        profile.age_range_max = None
        profile.distance_max_km = None
        profile.is_verified = False
        
        score = PrimaryRatingCalculator.calculate_completeness_score(profile)
        assert score == 0.0

    def test_completeness_score_full_profile(self):
        """Заполненный профиль должен иметь высокий score."""
        profile = MagicMock()
        profile.display_name = "Тест"
        profile.date_of_birth = date(1995, 1, 1)
        profile.gender = "male"
        profile.bio = "Это тестовый профиль с достаточным описанием для теста"
        profile.city = "Москва"
        profile.looking_for = "female"
        profile.interests = ["программирование", "музыка"]
        profile.height_cm = 180
        profile.age_range_min = 18
        profile.age_range_max = 100
        profile.distance_max_km = 100
        profile.is_verified = False
        
        score = PrimaryRatingCalculator.calculate_completeness_score(profile)
        assert score > 0.8

    def test_photo_score_zero_photos(self):
        """0 фото = 0 score."""
        score = PrimaryRatingCalculator.calculate_photo_score(0, False)
        assert score == 0.0

    def test_photo_score_many_photos(self):
        """4+ фото = высокий score (логарифмическая шкала)."""
        score = PrimaryRatingCalculator.calculate_photo_score(6, True)
        # 6 фото с primary дают ~0.76, что хорошо
        assert score > 0.7

    def test_verification_bonus(self):
        """Верифицированные пользователи получают бонус."""
        assert PrimaryRatingCalculator.calculate_verification_bonus(True) == 0.05
        assert PrimaryRatingCalculator.calculate_verification_bonus(False) == 0.0

    def test_total_calculation(self):
        """Тест полного расчёта первичного рейтинга."""
        profile = MagicMock()
        profile.display_name = "Тест"
        profile.bio = "Тестовый профиль с описанием"
        profile.city = "Москва"
        profile.interests = ["тест"]
        profile.is_verified = True
        profile.date_of_birth = None
        profile.gender = None
        profile.height_cm = None
        profile.age_range_min = None
        profile.age_range_max = None
        profile.distance_max_km = None
        
        result = PrimaryRatingCalculator.calculate_total(profile, 3, True)
        
        assert "completeness_score" in result
        assert "photo_score" in result
        assert "verification_bonus" in result
        assert "total_score" in result
        assert 0 <= result["total_score"] <= 1.0


class TestBehavioralRatingCalculator:
    """Тесты для Уровня 2: Поведенческий рейтинг."""

    def test_like_count_score_zero(self):
        """0 лайков = 0 score."""
        score = BehavioralRatingCalculator.calculate_like_count_score(0)
        assert score == 0.0

    def test_like_count_score_many(self):
        """100+ лайков = высокий score."""
        score = BehavioralRatingCalculator.calculate_like_count_score(100)
        assert score > 0.8

    def test_like_pass_ratio_perfect(self):
        """100% лайков = высокий score."""
        score = BehavioralRatingCalculator.calculate_like_pass_ratio_score(100, 0)
        assert score > 0.9

    def test_like_pass_ratio_terrible(self):
        """0% лайков = низкий score."""
        score = BehavioralRatingCalculator.calculate_like_pass_ratio_score(0, 100)
        assert score < 0.2

    def test_match_rate_score_zero(self):
        """0 мэтчей = 0 score."""
        score = BehavioralRatingCalculator.calculate_match_rate_score(0, 50)
        assert score == 0.0

    def test_match_rate_score_high(self):
        """20%+ мэтчей = максимальный score."""
        score = BehavioralRatingCalculator.calculate_match_rate_score(10, 50)
        assert score == 1.0

    def test_conversation_initiation_zero(self):
        """0 сообщений = низкий score."""
        score = BehavioralRatingCalculator.calculate_conversation_initiation_score(0, 10)
        assert score < 0.3

    def test_activity_pattern_inactive(self):
        """Неактивный пользователь = низкий score."""
        score = BehavioralRatingCalculator.calculate_activity_pattern_score(0, 60)
        assert score == 0.0

    def test_activity_pattern_active(self):
        """Активный пользователь = высокий score."""
        score = BehavioralRatingCalculator.calculate_activity_pattern_score(30, 0)
        assert score > 0.8


class TestCombinedRatingCalculator:
    """Тесты для Уровня 3: Комбинированный рейтинг."""

    def test_total_calculation(self):
        """Тест полного расчёта комбинированного рейтинга."""
        result = CombinedRatingCalculator.calculate_total(0.8, 0.7, 0.1)
        
        assert "primary_score" in result
        assert "behavioral_score" in result
        assert "referral_bonus" in result
        assert "total_score" in result
        assert "tier" in result
        assert 0 <= result["total_score"] <= 1.0

    def test_tier_assignment(self):
        """Тест назначения tier'ов."""
        assert CombinedRatingCalculator._assign_tier(0.95) == "S"
        assert CombinedRatingCalculator._assign_tier(0.80) == "A"
        assert CombinedRatingCalculator._assign_tier(0.65) == "B"
        assert CombinedRatingCalculator._assign_tier(0.50) == "C"
        assert CombinedRatingCalculator._assign_tier(0.35) == "D"
        assert CombinedRatingCalculator._assign_tier(0.10) == "E"

    def test_percentile_calculation(self):
        """Тест расчёта перцентиля."""
        all_scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        percentile = CombinedRatingCalculator.calculate_percentile(0.7, all_scores)
        assert percentile > 0.5

    def test_empty_percentile(self):
        """Пустой список = 0 перцентиль."""
        percentile = CombinedRatingCalculator.calculate_percentile(0.5, [])
        assert percentile == 0.0


# ============================================
# Photo Service Tests
# ============================================

class TestPhotoService:
    """Тесты для PhotoService."""

    @pytest.mark.asyncio
    async def test_validate_file_type_valid(self, mock_db_session):
        """Валидный тип файла должен проходить."""
        service = PhotoService(mock_db_session)
        mock_db_session.execute.return_value = MagicMock(scalar=MagicMock(return_value=0))
        
        result = await service.validate_upload(
            profile_id=str(uuid4()),
            filename="test.jpg",
            content_type="image/jpeg",
            file_size=1024 * 1024,  # 1 MB
        )
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_file_type_invalid(self, mock_db_session):
        """Невалидный тип файла должен отклоняться."""
        service = PhotoService(mock_db_session)
        
        result = await service.validate_upload(
            profile_id=str(uuid4()),
            filename="test.pdf",
            content_type="application/pdf",
            file_size=1024,
        )
        assert result["valid"] is False
        assert "Неподдерживаемый формат" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_file_size_too_large(self, mock_db_session):
        """Слишком большой файл должен отклоняться."""
        service = PhotoService(mock_db_session)
        
        result = await service.validate_upload(
            profile_id=str(uuid4()),
            filename="test.jpg",
            content_type="image/jpeg",
            file_size=15 * 1024 * 1024,  # 15 MB
        )
        assert result["valid"] is False
        assert "слишком большой" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_max_photos_reached(self, mock_db_session):
        """Превышение лимита фото должно отклоняться."""
        service = PhotoService(mock_db_session)
        mock_db_session.execute.return_value = MagicMock(scalar=MagicMock(return_value=6))
        
        result = await service.validate_upload(
            profile_id=str(uuid4()),
            filename="test.jpg",
            content_type="image/jpeg",
            file_size=1024,
        )
        assert result["valid"] is False
        assert "Максимум" in result["error"]

    def test_generate_s3_key(self, mock_db_session):
        """S3 ключ должен быть уникальным."""
        service = PhotoService(mock_db_session)
        profile_id = str(uuid4())
        
        key1 = service.generate_s3_key(profile_id, "photo.jpg")
        key2 = service.generate_s3_key(profile_id, "photo.jpg")
        
        assert key1 != key2  # UUID делает их уникальными
        assert profile_id in key1
        assert key1.endswith(".jpg")


# ============================================
# Matching Service Tests
# ============================================

class TestMatchingService:
    """Тесты для MatchingService."""

    def test_service_initialization(self, mock_db_session):
        """MatchingService должен инициализироваться."""
        from backend.services.matching_service import MatchingService
        
        service = MatchingService(mock_db_session)
        assert service.PROFILES_PER_SESSION == 10
        assert service.CACHE_TTL == 3600

    def test_calculate_age(self):
        """Тест расчёта возраста."""
        from backend.services.matching_service import MatchingService
        from datetime import date
        
        birth_date = date(1995, 1, 1)
        age = MatchingService._calculate_age(birth_date)
        
        expected_age = date.today().year - 1995
        if (date.today().month, date.today().day) < (birth_date.month, birth_date.day):
            expected_age -= 1
        
        assert age == expected_age


# ============================================
# Redis Cache Tests (integration)
# ============================================

class TestRedisCachePatterns:
    """Тесты для Redis cache паттернов (без реального Redis)."""

    def test_profile_session_cache_initialization(self):
        """ProfileSessionCache должен инициализироваться."""
        mock_redis = AsyncMock()
        cache = ProfileSessionCache(mock_redis)
        assert cache.redis == mock_redis

    def test_rating_cache_initialization(self):
        """RatingCache должен инициализироваться."""
        mock_redis = AsyncMock()
        cache = RatingCache(mock_redis)
        assert cache.redis == mock_redis

    def test_swipe_counter_cache_initialization(self):
        """SwipeCounterCache должен инициализироваться."""
        mock_redis = AsyncMock()
        cache = SwipeCounterCache(mock_redis)
        assert cache.redis == mock_redis
