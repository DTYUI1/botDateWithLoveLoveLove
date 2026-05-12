"""Тесты soft city-фильтра в `MatchingService`.

Проверяем:
1. `_apply_preferences_filters(..., include_city=True)` добавляет в SQL
   условие на `profiles.city == ...` — это исходное «строгое» поведение.
2. `_apply_preferences_filters(..., include_city=False)` НЕ добавляет
   city-фильтр — это путь soft fallback.
3. `get_matching_profiles` при пустом первом проходе действительно делает
   повторный запрос без city и возвращает кандидата.

Используем уже доступную в `tests/conftest.py` инфраструктуру (mock-сессию
и `MockDBResult`), чтобы не поднимать реальную БД.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from models.profile import Profile
from models.rating import RatingCombined as RatingCombinedModel
from services.matching_service import MatchingService
from tests.conftest import MockDBResult


def _make_profile(*, city: str | None = "Сириус", looking_for: str = "female", age_min: int = 18, age_max: int = 60):
    profile = MagicMock(spec=Profile)
    profile.id = uuid4()
    profile.city = city
    profile.looking_for = looking_for
    profile.age_range_min = age_min
    profile.age_range_max = age_max
    profile.gender = "male"
    profile.date_of_birth = date(1997, 5, 12)
    profile.is_active = True
    return profile


def _query_text(query) -> str:
    """Скомпилировать SQLAlchemy-запрос в текст SQL для проверки WHERE-условий."""
    compiled = query.compile(compile_kwargs={"literal_binds": True})
    return str(compiled)


def test_apply_preferences_filters_includes_city_by_default(mock_db_session):
    """Дефолтное поведение: city-фильтр включён в WHERE."""
    service = MatchingService(mock_db_session)
    my_profile = _make_profile(city="Сириус")

    base = select(Profile, RatingCombinedModel.total_score)
    query = service._apply_preferences_filters(base, my_profile)

    sql = _query_text(query)
    assert "profiles.city = 'Сириус'" in sql


def test_apply_preferences_filters_drops_city_when_include_city_false(mock_db_session):
    """Soft fallback: city-фильтр отключён."""
    service = MatchingService(mock_db_session)
    my_profile = _make_profile(city="Сириус")

    base = select(Profile, RatingCombinedModel.total_score)
    query = service._apply_preferences_filters(base, my_profile, include_city=False)

    sql = _query_text(query)
    # В SELECT-листе profiles.city может встречаться как колонка — проверяем
    # именно WHERE-условие.
    assert "profiles.city =" not in sql
    # Остальные фильтры всё ещё должны быть на месте
    assert "profiles.gender" in sql  # looking_for→gender


@pytest.mark.asyncio
async def test_get_matching_profiles_soft_fallback(mock_db_session):
    """
    Если первый проход вернул 0 строк, сервис делает второй запрос (без city)
    и возвращает кандидата из fallback-результата.
    """
    service = MatchingService(mock_db_session)
    me_user = MagicMock()
    me_user.id = uuid4()
    me_profile = _make_profile(city="Москва")

    candidate_profile = _make_profile(city="Сириус")
    candidate_profile.display_name = "Анна"
    candidate_profile.bio = "test bio"
    candidate_profile.interests = ["книги"]

    # Photo для кандидата — нужен, чтобы попасть в выдачу и в финальный dict.
    photo = MagicMock()
    photo.id = uuid4()
    photo.profile_id = candidate_profile.id
    photo.is_primary = True
    photo.sort_order = 0

    # Последовательность вызовов db.execute:
    # 1) выбираем User по telegram_id            → me_user
    # 2) выбираем Profile по user_id             → me_profile
    # 3) выбираем swiped_ids                      → пусто
    # 4) первый проход кандидатов (strict)        → пусто  ← триггерит fallback
    # 5) второй проход кандидатов (soft)          → [(candidate_profile, 0.5)]
    # 6) выбираем photos для found profiles       → [photo]
    # 7) выбираем username по Profile.id          → [(candidate_profile.id, "anna")]
    rating_score = 0.5
    side_effects = [
        MockDBResult([me_user]),
        MockDBResult([me_profile]),
        MockDBResult([]),                                  # swiped_ids
        MagicMock(all=MagicMock(return_value=[])),         # strict pass — пусто
        MagicMock(all=MagicMock(return_value=[(candidate_profile, rating_score)])),
        # фотки: scalars().all() → [photo]
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[photo])))),
        # username: result.all() → list of tuples
        MagicMock(all=MagicMock(return_value=[(candidate_profile.id, "anna")])),
    ]
    mock_db_session.execute = AsyncMock(side_effect=side_effects)

    profiles = await service.get_matching_profiles(telegram_id=42)

    # Должны вернуть единственного кандидата из soft fallback
    assert len(profiles) == 1
    assert profiles[0]["display_name"] == "Анна"
    assert profiles[0]["username"] == "anna"
    # Подтверждаем, что execute дёрнули именно 7 раз — fallback состоялся
    assert mock_db_session.execute.await_count == 7
