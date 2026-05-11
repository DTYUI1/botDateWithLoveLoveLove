"""Singleton-доступ к RabbitMQ event publisher.

Закрывает три проблемы аудита (блоки 3.8, 3.9):

* Persistent connection через `aio_pika.connect_robust` — не пересоздаём
  TCP-сессию на каждый свайп.
* Топология (exchanges + queues + bindings) декларируется один раз при старте,
  на горячем пути остаётся только `exchange.publish()`.
* Fail-safe: ошибки публикации логируются, но не валят HTTP-ответ.

Используется в lifespan приложения:

    from core.mq import init_event_publisher, close_event_publisher
    await init_event_publisher()      # startup
    await close_event_publisher()     # shutdown

И на горячем пути:

    publisher = get_event_publisher()
    await publisher.publish_swipe_event(...)
"""

from __future__ import annotations

import asyncio
from typing import Optional

from loguru import logger

from core.config import settings
from infrastructure.rabbitmq.event_publisher import EventPublisher


_publisher: Optional[EventPublisher] = None
_lock = asyncio.Lock()


async def init_event_publisher() -> Optional[EventPublisher]:
    """Создать singleton publisher и задекларировать топологию.

    Возвращает None если RabbitMQ недоступен — это не валит startup.
    Декларация exchanges/queues/bindings происходит ровно один раз;
    дальше на горячем пути остаётся только publish.
    """
    global _publisher
    if _publisher is not None and _publisher.connection and not _publisher.connection.is_closed:
        return _publisher
    async with _lock:
        if _publisher is not None and _publisher.connection and not _publisher.connection.is_closed:
            return _publisher
        publisher = EventPublisher(settings.rabbitmq_url)
        try:
            await publisher.connect()
            _publisher = publisher
            logger.info("✅ RabbitMQ publisher singleton поднят, топология декларирована")
            return _publisher
        except Exception as e:
            logger.warning(f"⚠️ RabbitMQ publisher init failed: {type(e).__name__}: {e}")
            return None


def get_event_publisher() -> Optional[EventPublisher]:
    """Вернуть текущий singleton (без инициализации)."""
    return _publisher


async def close_event_publisher() -> None:
    global _publisher
    if _publisher is None:
        return
    try:
        await _publisher.close()
        logger.info("✅ RabbitMQ publisher закрыт")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка закрытия RabbitMQ publisher: {type(e).__name__}: {e}")
    finally:
        _publisher = None


async def safe_publish(coro_factory, *, op: str) -> bool:
    """Обёртка для fail-safe публикации.

    Принимает фабрику корутины (lambda: publisher.publish_xxx(...)) и
    логирует ошибки без выброса исключений наружу. Возвращает True/False
    для метрик / тестов.
    """
    from core.metrics import MQ_PUBLISH_ERRORS, MQ_PUBLISH_OK

    publisher = get_event_publisher()
    if publisher is None:
        logger.debug(f"[MQ] publisher не инициализирован, пропуск {op}")
        MQ_PUBLISH_ERRORS.labels(op=op).inc()
        return False
    try:
        await coro_factory(publisher)
        MQ_PUBLISH_OK.labels(op=op).inc()
        return True
    except Exception as e:
        logger.warning(f"[MQ] публикация {op} не удалась: {type(e).__name__}: {e}")
        MQ_PUBLISH_ERRORS.labels(op=op).inc()
        return False
