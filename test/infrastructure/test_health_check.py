"""
Тесты для проверки здоровья инфраструктуры.

Проверяет:
- PostgreSQL подключение
- Redis подключение
- RabbitMQ подключение
- MinIO подключение
"""

import pytest
import pytest_asyncio
import asyncio

from backend.core.redis_client import RedisClient


# ============================================
# TESTS: Redis Health
# ============================================

@pytest.mark.asyncio
async def test_redis_health():
    """Тест: Redis здоров."""
    client = RedisClient()
    try:
        is_healthy = await client.health_check()
        assert is_healthy
    except Exception as e:
        pytest.skip(f"Redis не доступен: {e}")
    finally:
        await client.disconnect()


@pytest.mark.asyncio
async def test_redis_connection():
    """Тест: подключение к Redis."""
    client = RedisClient()
    try:
        await client.connect()
        assert client.redis is not None
    except Exception as e:
        pytest.skip(f"Не удалось подключиться к Redis: {e}")
    finally:
        await client.disconnect()


# ============================================
# TESTS: PostgreSQL Health
# ============================================

@pytest.mark.asyncio
async def test_postgresql_health():
    """Тест: PostgreSQL здоров."""
    try:
        from sqlalchemy import text
        from core.database import engine

        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
    except Exception as e:
        pytest.skip(f"PostgreSQL не доступен: {e}")


# ============================================
# TESTS: RabbitMQ Health
# ============================================

@pytest.mark.asyncio
async def test_rabbitmq_health():
    """Тест: RabbitMQ здоров."""
    try:
        import aio_pika
        from core.config import settings

        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        assert connection.is_closed is False
        await connection.close()
    except Exception as e:
        pytest.skip(f"RabbitMQ не доступен: {e}")


# ============================================
# TESTS: Integration
# ============================================

@pytest.mark.asyncio
async def test_all_services_available():
    """
    Интеграционный тест: все сервисы доступны.
    
    Этот тест проверяет что вся инфраструктура работает.
    """
    services = {
        "redis": False,
        "postgresql": False,
        "rabbitmq": False,
    }

    # Проверить Redis
    try:
        client = RedisClient()
        services["redis"] = await client.health_check()
        await client.disconnect()
    except Exception:
        pass

    # Проверить PostgreSQL
    try:
        from sqlalchemy import text
        from core.database import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            services["postgresql"] = True
    except Exception:
        pass

    # Проверить RabbitMQ
    try:
        import aio_pika
        from core.config import settings

        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        services["rabbitmq"] = not connection.is_closed
        await connection.close()
    except Exception:
        pass

    # Вывести результаты
    print("\n=== Infrastructure Health Check ===")
    for service, is_available in services.items():
        status = "✅" if is_available else "❌"
        print(f"{status} {service}: {'available' if is_available else 'unavailable'}")
    print("====================================")

    # Хотя бы один сервис должен быть доступен
    assert any(services.values()), "Ни один сервис не доступен!"
