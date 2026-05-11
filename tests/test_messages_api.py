"""
Unit-тесты MessageService (backend/services/message_service.py).

Тестируют логику без реальной БД — все вызовы AsyncSession мокированы.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.message_service import MessageService
from schemas.message import MessageCreate
from tests.conftest import MockDBResult


@pytest.fixture
def message_service(mock_db_session):
    return MessageService(mock_db_session)


@pytest.fixture
def fake_match():
    match = MagicMock()
    match.id = uuid4()
    match.profile1_id = uuid4()
    match.profile2_id = uuid4()
    match.status = "active"
    match.message_count = 0
    match.last_message_at = None
    match.last_message_preview = None
    match.updated_at = None
    return match


@pytest.mark.asyncio
async def test_send_message_success(message_service, mock_db_session, fake_match):
    """Отправка валидного сообщения создаёт запись и обновляет мэтч."""
    sender_id = fake_match.profile1_id
    mock_db_session.execute.return_value = MockDBResult([fake_match])

    data = MessageCreate(content="Привет!", message_type="text")
    msg = await message_service.send_message(fake_match.id, sender_id, data)

    mock_db_session.add.assert_called_once()
    assert fake_match.message_count == 1
    assert fake_match.last_message_preview == "Привет!"
    assert fake_match.last_message_at is not None
    assert msg.content == "Привет!"
    assert msg.sender_id == sender_id


@pytest.mark.asyncio
async def test_send_message_match_not_found(message_service, mock_db_session):
    """Если мэтч не принадлежит профилю — ValueError."""
    mock_db_session.execute.return_value = MockDBResult(None)

    data = MessageCreate(content="hi")
    with pytest.raises(ValueError, match="Мэтч не найден"):
        await message_service.send_message(uuid4(), uuid4(), data)


@pytest.mark.asyncio
async def test_send_message_empty_rejected(message_service, mock_db_session, fake_match):
    """Пустое сообщение без media — ValueError."""
    mock_db_session.execute.return_value = MockDBResult([fake_match])
    data = MessageCreate(content=None, media_urls=[])
    with pytest.raises(ValueError, match="не может быть пустым"):
        await message_service.send_message(fake_match.id, fake_match.profile1_id, data)


@pytest.mark.asyncio
async def test_list_messages_returns_pagination(message_service, mock_db_session, fake_match):
    """list_messages возвращает (items, total)."""
    msg1 = MagicMock(id=uuid4(), match_id=fake_match.id)
    msg2 = MagicMock(id=uuid4(), match_id=fake_match.id)

    match_result = MockDBResult([fake_match])
    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=2)
    list_result = MockDBResult([msg1, msg2])

    mock_db_session.execute = AsyncMock(side_effect=[match_result, count_result, list_result])

    items, total = await message_service.list_messages(
        fake_match.id, fake_match.profile1_id, limit=10, offset=0
    )
    assert total == 2
    assert len(items) == 2


@pytest.mark.asyncio
async def test_list_messages_match_not_found(message_service, mock_db_session):
    mock_db_session.execute.return_value = MockDBResult(None)
    with pytest.raises(ValueError):
        await message_service.list_messages(uuid4(), uuid4(), 10, 0)


@pytest.mark.asyncio
async def test_message_create_schema_strips_whitespace():
    """Валидатор схемы обрезает пробелы и пустую строку приводит к None."""
    m = MessageCreate(content="   hello  ")
    assert m.content == "hello"

    m2 = MessageCreate(content="   ", media_urls=["x"])
    assert m2.content is None
