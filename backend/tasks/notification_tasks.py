"""Celery tasks для push-уведомлений.

`send_match_push` — публикует событие в RabbitMQ (`match_events`), затем
bot/workers/match_consumer.py доставляет push в Telegram.

Это даёт fan-out на боте независимо от HTTP-цикла.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from celery_app import celery_app
from core.mq import init_event_publisher


async def _send_match_push(match_id: Any, user1_id: Any, user2_id: Any) -> dict:
    publisher = await init_event_publisher()
    if publisher is None:
        logger.warning("[Celery notify] publisher недоступен, push не отправлен")
        return {"status": "skipped", "match_id": str(match_id)}
    await publisher.publish_match_event(
        user1_id=user1_id, user2_id=user2_id, match_id=match_id,
    )
    return {"status": "ok", "match_id": str(match_id)}


@celery_app.task(name="backend.send_match_push")
def send_match_push(match_id: Any, user1_id: Any, user2_id: Any) -> dict:
    return asyncio.run(_send_match_push(match_id, user1_id, user2_id))
