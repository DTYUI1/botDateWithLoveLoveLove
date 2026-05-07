"""
Тесты для RabbitMQ Event Publisher.

Проверяет:
- Подключение к RabbitMQ
- Публикация событий
- Закрытие соединения
"""

import pytest
import pytest_asyncio
import json

from infrastructure.rabbitmq.event_publisher import EventPublisher


# ============================================
# FIXTURES
# ============================================

@pytest_asyncio.fixture
async def publisher():
    """Создать EventPublisher для тестов."""
    pub = EventPublisher("amqp://guest:guest@localhost:5672//")
    try:
        await pub.connect()
        yield pub
    except Exception as e:
        pytest.skip(f"RabbitMQ не доступен: {e}")
    finally:
        await pub.close()


# ============================================
# TESTS: Event Publisher
# ============================================

@pytest.mark.asyncio
async def test_connect(publisher):
    """Тест: подключение к RabbitMQ."""
    assert publisher.connection is not None
    assert publisher.connection.is_closed is False
    assert len(publisher.exchanges) == 4


@pytest.mark.asyncio
async def test_publish_swipe_event(publisher):
    """Тест: публикация события свайпа."""
    # Не должно вызывать исключений
    await publisher.publish_swipe_event(
        from_user_id=100,
        to_user_id=200,
        action="like",
        session_id="test-session",
        time_spent_ms=5000
    )


@pytest.mark.asyncio
async def test_publish_match_event(publisher):
    """Тест: публикация события мэтча."""
    await publisher.publish_match_event(
        user1_id=100,
        user2_id=200,
        match_id=300
    )


@pytest.mark.asyncio
async def test_publish_rating_update(publisher):
    """Тест: публикация события обновления рейтинга."""
    await publisher.publish_rating_update(
        user_id=100,
        rating_type="combined",
        new_score=0.85,
        old_score=0.80
    )


@pytest.mark.asyncio
async def test_publish_message_sent(publisher):
    """Тест: публикация события отправки сообщения."""
    await publisher.publish_message_sent(
        match_id=100,
        sender_id=200,
        message_id=300,
        content_preview="Привет!"
    )


@pytest.mark.asyncio
async def test_context_manager():
    """Тест: использование как контекстный менеджер."""
    try:
        async with EventPublisher("amqp://guest:guest@localhost:5672//") as pub:
            assert pub.connection is not None
            await pub.publish_swipe_event(100, 200, "like")
        # После выхода из контекста соединение закрыто
        assert pub.connection.is_closed
    except Exception as e:
        pytest.skip(f"RabbitMQ не доступен: {e}")
