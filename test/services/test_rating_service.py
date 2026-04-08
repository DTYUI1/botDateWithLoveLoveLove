"""
Тесты для RatingService.

Проверяет:
- Уровень 1: Первичный рейтинг
- Уровень 2: Поведенческий рейтинг
- Уровень 3: Комбинированный рейтинг
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import date

from backend.services.rating_service import (
    PrimaryRatingCalculator,
    BehavioralRatingCalculator,
    CombinedRatingCalculator,
)


# ============================================
# TESTS: Уровень 1 - Первичный рейтинг
# ============================================

class TestPrimaryRatingCalculator:
    """Тесты калькулятора первичного рейтинга."""

    def test_calculate_completeness_score_full_profile(self):
        """Тест: заполненный профиль = высокий score."""
        profile = Mock()
        profile.display_name = "Alice"
        profile.date_of_birth = date(1995, 5, 15)
        profile.gender = "female"
        profile.bio = "I love hiking and photography!"
        profile.city = "Moscow"
        profile.looking_for = "male"
        profile.interests = ["hiking", "photography", "travel"]
        profile.height_cm = 170
        profile.age_range_min = 25
        profile.age_range_max = 35
        profile.distance_max_km = 50

        score = PrimaryRatingCalculator.calculate_completeness_score(profile)
        assert score > 0.9  # Почти полный профиль

    def test_calculate_completeness_score_empty_profile(self):
        """Тест: пустой профиль = низкий score."""
        profile = Mock()
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

        score = PrimaryRatingCalculator.calculate_completeness_score(profile)
        assert score == 0.0

    def test_calculate_photo_score_many_photos(self):
        """Тест: много фото = высокий score."""
        score = PrimaryRatingCalculator.calculate_photo_score(5, True)
        assert score > 0.7  # 5 фото с главным = ~0.76

    def test_calculate_photo_score_no_photos(self):
        """Тест: нет фото = 0."""
        score = PrimaryRatingCalculator.calculate_photo_score(0, False)
        assert score == 0.0

    def test_calculate_verification_bonus_verified(self):
        """Тест: бонус за верификацию."""
        bonus = PrimaryRatingCalculator.calculate_verification_bonus(True)
        assert bonus == 0.05

    def test_calculate_verification_bonus_not_verified(self):
        """Тест: нет бонуса без верификации."""
        bonus = PrimaryRatingCalculator.calculate_verification_bonus(False)
        assert bonus == 0.0

    def test_calculate_total(self):
        """Тест: полный расчёт первичного рейтинга."""
        profile = Mock()
        profile.display_name = "Alice"
        profile.date_of_birth = date(1995, 5, 15)
        profile.gender = "female"
        profile.bio = "Love hiking!"
        profile.city = "Moscow"
        profile.looking_for = "male"
        profile.interests = ["hiking"]
        profile.height_cm = 170
        profile.age_range_min = 25
        profile.age_range_max = 35
        profile.distance_max_km = 50
        profile.is_verified = True

        result = PrimaryRatingCalculator.calculate_total(profile, 3, True)
        
        assert "completeness_score" in result
        assert "photo_score" in result
        assert "verification_bonus" in result
        assert "total_score" in result
        assert result["total_score"] > 0.5


# ============================================
# TESTS: Уровень 2 - Поведенческий рейтинг
# ============================================

class TestBehavioralRatingCalculator:
    """Тесты калькулятора поведенческого рейтинга."""

    def test_calculate_like_count_score_many_likes(self):
        """Тест: много лайков = высокий score."""
        score = BehavioralRatingCalculator.calculate_like_count_score(100)
        assert score > 0.8

    def test_calculate_like_count_score_no_likes(self):
        """Тест: нет лайков = 0."""
        score = BehavioralRatingCalculator.calculate_like_count_score(0)
        assert score == 0.0

    def test_calculate_like_pass_ratio_high_ratio(self):
        """Тест: высокое соотношение лайков/пропусков."""
        score = BehavioralRatingCalculator.calculate_like_pass_ratio_score(80, 20)
        assert score > 0.8

    def test_calculate_like_pass_ratio_low_ratio(self):
        """Тест: низкое соотношение."""
        score = BehavioralRatingCalculator.calculate_like_pass_ratio_score(20, 80)
        assert score < 0.2

    def test_calculate_match_rate_score_high_rate(self):
        """Тест: высокая частота мэтчей."""
        score = BehavioralRatingCalculator.calculate_match_rate_score(20, 50)  # 40%
        assert score > 0.9

    def test_calculate_match_rate_score_no_matches(self):
        """Тест: нет мэтчей = 0."""
        score = BehavioralRatingCalculator.calculate_match_rate_score(0, 50)
        assert score == 0.0

    def test_calculate_activity_pattern_active(self):
        """Тест: активный пользователь = высокий score."""
        score = BehavioralRatingCalculator.calculate_activity_pattern_score(
            days_active=60,
            last_active_days_ago=0
        )
        assert score > 0.8

    def test_calculate_activity_pattern_inactive(self):
        """Тест: неактивный пользователь = низкий score."""
        score = BehavioralRatingCalculator.calculate_activity_pattern_score(
            days_active=5,
            last_active_days_ago=60
        )
        assert score < 0.3

    def test_calculate_total(self):
        """Тест: полный расчёт поведенческого рейтинга."""
        result = BehavioralRatingCalculator.calculate_total(
            like_received_count=50,
            pass_received_count=20,
            matches_count=15,
            total_swipes=50,
            messages_sent=10,
            days_active=30,
            last_active_days_ago=1
        )

        assert "total_score" in result
        assert result["total_score"] > 0.5


# ============================================
# TESTS: Уровень 3 - Комбинированный рейтинг
# ============================================

class TestCombinedRatingCalculator:
    """Тесты калькулятора комбинированного рейтинга."""

    def test_calculate_total_high_scores(self):
        """Тест: высокие score = высокий комбинированный рейтинг."""
        result = CombinedRatingCalculator.calculate_total(
            primary_score=0.9,
            behavioral_score=0.85,
            referral_bonus=0.05
        )

        assert result["total_score"] > 0.7
        assert result["tier"] in ["S", "A"]

    def test_calculate_total_low_scores(self):
        """Тест: низкие score = низкий комбинированный рейтинг."""
        result = CombinedRatingCalculator.calculate_total(
            primary_score=0.2,
            behavioral_score=0.1,
            referral_bonus=0.0
        )

        assert result["total_score"] < 0.3
        assert result["tier"] in ["D", "E"]

    def test_assign_tier_s(self):
        """Тест: назначение tier S."""
        tier = CombinedRatingCalculator._assign_tier(0.95)
        assert tier == "S"

    def test_assign_tier_a(self):
        """Тест: назначение tier A."""
        tier = CombinedRatingCalculator._assign_tier(0.80)
        assert tier == "A"

    def test_assign_tier_c(self):
        """Тест: назначение tier C."""
        tier = CombinedRatingCalculator._assign_tier(0.50)
        assert tier == "C"

    def test_assign_tier_e(self):
        """Тест: назначение tier E."""
        tier = CombinedRatingCalculator._assign_tier(0.10)
        assert tier == "E"

    def test_calculate_percentile(self):
        """Тест: расчёт перцентиля."""
        all_scores = [0.2, 0.4, 0.5, 0.6, 0.8]
        percentile = CombinedRatingCalculator.calculate_percentile(0.6, all_scores)
        
        assert percentile == 0.6  # 60% ниже

    def test_weights_sum(self):
        """Тест: веса должны давать разумный total."""
        result = CombinedRatingCalculator.calculate_total(
            primary_score=0.5,
            behavioral_score=0.5,
            referral_bonus=0.5
        )

        # Проверить формулу: 0.5*0.4 + 0.5*0.5 + 0.5*0.1 = 0.5
        expected = 0.5 * 0.40 + 0.5 * 0.50 + 0.5 * 0.10
        assert abs(result["total_score"] - expected) < 0.001
