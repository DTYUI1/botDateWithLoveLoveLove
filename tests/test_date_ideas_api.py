"""
Unit-тесты DateIdeaService (backend/services/date_idea_service.py).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.date_idea_service import DateIdeaService
from schemas.date_idea import DateIdeaCreate
from tests.conftest import MockDBResult


@pytest.fixture
def service(mock_db_session):
    return DateIdeaService(mock_db_session)


def _make_idea(title="Прогулка в парке", city="Москва", interests=None,
               positive=0, suggested=0, category="outdoor"):
    idea = MagicMock()
    idea.id = uuid4()
    idea.title = title
    idea.city = city
    idea.category = category
    idea.suitable_interests = interests or []
    idea.positive_feedback_count = positive
    idea.suggested_count = suggested
    idea.is_active = True
    return idea


@pytest.mark.asyncio
async def test_create_idea(service, mock_db_session):
    data = DateIdeaCreate(category="cafe", title="Уютная кофейня", city="Москва")
    idea = await service.create_idea(data)
    mock_db_session.add.assert_called_once()
    mock_db_session.flush.assert_awaited()
    assert idea.title == "Уютная кофейня"


@pytest.mark.asyncio
async def test_list_ideas_filters_by_city_and_category(service, mock_db_session):
    items = [_make_idea(city="Москва", category="cafe")]
    mock_db_session.execute.return_value = MockDBResult(items)
    result = await service.list_ideas(city="Москва", category="cafe", limit=5)
    assert len(result) == 1
    mock_db_session.execute.assert_awaited()


@pytest.mark.asyncio
async def test_suggest_for_user_no_profile(service, mock_db_session):
    mock_db_session.execute.return_value = MockDBResult(None)
    with pytest.raises(ValueError, match="Профиль не найден"):
        await service.suggest_for_user(telegram_id=999)


@pytest.mark.asyncio
async def test_suggest_for_user_ranks_by_city_and_interests(service, mock_db_session):
    """suggest_for_user должен учитывать город и интересы пользователя при ранжировании."""
    profile = MagicMock()
    profile.id = uuid4()
    profile.city = "Москва"
    profile.interests = ["музыка", "кино"]

    idea_relevant = _make_idea(city="Москва", interests=["музыка", "кино"], positive=5)
    idea_other_city = _make_idea(city="Питер", interests=["музыка"], positive=10)
    idea_irrelevant = _make_idea(city="Москва", interests=["спорт"], positive=2)

    profile_result = MockDBResult([profile])
    list_result = MockDBResult([idea_relevant, idea_other_city, idea_irrelevant])
    mock_db_session.execute = AsyncMock(side_effect=[profile_result, list_result])

    suggestions = await service.suggest_for_user(telegram_id=1, limit=3)

    assert suggestions[0] is idea_relevant
    assert idea_relevant.suggested_count == 1
    mock_db_session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_add_feedback_positive_increments_counter(service, mock_db_session):
    idea = _make_idea(positive=3)
    mock_db_session.execute.return_value = MockDBResult([idea])
    result = await service.add_feedback(idea.id, positive=True)
    assert result is idea
    assert idea.positive_feedback_count == 4


@pytest.mark.asyncio
async def test_add_feedback_idea_not_found(service, mock_db_session):
    mock_db_session.execute.return_value = MockDBResult(None)
    result = await service.add_feedback(uuid4(), positive=True)
    assert result is None


def test_create_schema_validates_category():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        DateIdeaCreate(category="bogus", title="Hello world")
