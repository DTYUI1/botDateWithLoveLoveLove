"""
Тесты для Redis кэширования.

Проверяет:
- ProfileSessionCache
- RatingCache
- SwipeCounterCache
"""

import pytest
import pytest_asyncio
import redis.asyncio as redis

from infrastructure.redis.cache_patterns import (
    ProfileSessionCache,
    RatingCache,
    SwipeCounterCache,
)


# ============================================
# FIXTURES
# ============================================

@pytest_asyncio.fixture
async def redis_client():
    """Создать Redis клиент для тестов."""
    client = redis.from_url("redis://localhost:6379/15", decode_responses=True)
    yield client
    # Очистить после теста
    await client.flushdb()
    await client.close()


@pytest_asyncio.fixture
async def session_cache(redis_client):
    return ProfileSessionCache(redis_client)


@pytest_asyncio.fixture
async def rating_cache(redis_client):
    return RatingCache(redis_client)


@pytest_asyncio.fixture
async def swipe_counter(redis_client):
    return SwipeCounterCache(redis_client)


# ============================================
# TESTS: ProfileSessionCache
# ============================================

@pytest.mark.asyncio
async def test_cache_profiles(session_cache):
    """Тест: кэширование анкет."""
    user_id = 12345
    session_id = "test-session-1"
    profiles = [
        {"id": "1", "name": "Alice", "age": 25},
        {"id": "2", "name": "Bob", "age": 27},
        {"id": "3", "name": "Charlie", "age": 30},
    ]

    await session_cache.cache_profiles(user_id, session_id, profiles)

    # Проверить что сессия закэширована
    assert await session_cache.is_session_cached(user_id, session_id)

    # Проверить количество
    count = await session_cache.get_remaining_count(user_id, session_id)
    assert count == 3


@pytest.mark.asyncio
async def test_get_next_profile(session_cache):
    """Тест: получение следующей анкеты из кэша."""
    user_id = 12345
    session_id = "test-session-2"
    profiles = [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Bob"},
    ]

    await session_cache.cache_profiles(user_id, session_id, profiles)

    # Получить первую анкету
    profile1 = await session_cache.get_next_profile(user_id, session_id)
    assert profile1["id"] == "1"

    # Получить вторую анкету
    profile2 = await session_cache.get_next_profile(user_id, session_id)
    assert profile2["id"] == "2"

    # Кэш пуст
    profile3 = await session_cache.get_next_profile(user_id, session_id)
    assert profile3 is None


@pytest.mark.asyncio
async def test_clear_session(session_cache):
    """Тест: очистка сессии."""
    user_id = 12345
    session_id = "test-session-3"
    profiles = [{"id": "1", "name": "Alice"}]

    await session_cache.cache_profiles(user_id, session_id, profiles)
    await session_cache.clear_session(user_id, session_id)

    assert not await session_cache.is_session_cached(user_id, session_id)


# ============================================
# TESTS: RatingCache
# ============================================

@pytest.mark.asyncio
async def test_update_rating(rating_cache):
    """Тест: обновление рейтинга."""
    await rating_cache.update_rating("combined", 100, 0.85)

    score = await rating_cache.get_user_score("combined", 100)
    assert score == 0.85


@pytest.mark.asyncio
async def test_get_top_profiles(rating_cache):
    """Тест: получение топ профилей."""
    # Добавить рейтинги
    await rating_cache.batch_update_ratings("combined", {
        1: 0.90,
        2: 0.85,
        3: 0.95,
        4: 0.70,
    })

    top = await rating_cache.get_top_profiles("combined", limit=3)
    assert len(top) == 3
    assert top[0] == 3  # Высший score
    assert top[1] == 1
    assert top[2] == 2


@pytest.mark.asyncio
async def test_get_user_rank(rating_cache):
    """Тест: получение позиции в рейтинге."""
    await rating_cache.batch_update_ratings("combined", {
        1: 0.80,
        2: 0.90,
        3: 0.70,
    })

    rank = await rating_cache.get_user_rank("combined", 2)
    assert rank == 1  # Первое место

    rank = await rating_cache.get_user_rank("combined", 1)
    assert rank == 2  # Второе место


# ============================================
# TESTS: SwipeCounterCache
# ============================================

@pytest.mark.asyncio
async def test_increment_swipe(swipe_counter):
    """Тест: инкремент счётчика свайпов."""
    user_id = 12345
    
    await swipe_counter.increment_swipe(user_id, "like")
    await swipe_counter.increment_swipe(user_id, "like")
    await swipe_counter.increment_swipe(user_id, "pass")

    stats = await swipe_counter.get_swipe_stats(user_id)
    assert stats["like"] == 2
    assert stats["pass"] == 1


@pytest.mark.asyncio
async def test_get_total_swipes(swipe_counter):
    """Тест: получение общего количества свайпов."""
    user_id = 12345
    
    await swipe_counter.increment_swipe(user_id, "like")
    await swipe_counter.increment_swipe(user_id, "pass")
    await swipe_counter.increment_swipe(user_id, "super_like")

    total = await swipe_counter.get_total_swipes(user_id)
    assert total == 3


@pytest.mark.asyncio
async def test_has_reached_limit(swipe_counter):
    """Тест: проверка достижения лимита."""
    user_id = 12345
    limit = 5

    # Добавить 3 свайпа
    for _ in range(3):
        await swipe_counter.increment_swipe(user_id, "like")

    assert not await swipe_counter.has_reached_limit(user_id, limit)

    # Добавить ещё 2
    await swipe_counter.increment_swipe(user_id, "like")
    await swipe_counter.increment_swipe(user_id, "like")

    assert await swipe_counter.has_reached_limit(user_id, limit)
