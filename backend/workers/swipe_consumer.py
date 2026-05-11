"""Consumer событий свайпов.

Слушает очередь `swipe_processing` и на каждом событии:

* Триггерит точечный пересчёт рейтинга получателя свайпа (Celery task
  `backend.recalculate_profile_rating`, см. `backend/tasks/rating_tasks.py`).

Запуск (локально):

    cd backend && python -m workers.swipe_consumer

В compose поднимается отдельным сервисом `swipe_consumer`.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from loguru import logger

from core.config import settings
from workers.base_consumer import BaseConsumer


class SwipeConsumer(BaseConsumer):
    queue_name = "swipe_processing"
    max_retries = 3

    async def handle(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> None:
        to_user_id = payload.get("to_user_id")
        action = payload.get("action")
        log = logger.bind(to_user_id=to_user_id, action=action)
        if not to_user_id:
            log.warning("[SwipeConsumer] payload без to_user_id, пропуск")
            return

        # Импорт celery-таски лениво — чтобы при отсутствии Celery в окружении
        # тест-консьюмера всё равно поднимался.
        try:
            from tasks.rating_tasks import recalculate_profile_rating
            recalculate_profile_rating.delay(profile_id=to_user_id)
            log.info("[SwipeConsumer] триггер точечного пересчёта рейтинга")
        except Exception as e:
            log.warning(f"[SwipeConsumer] не удалось отправить Celery task: {e}")
            raise


async def main() -> None:
    consumer = SwipeConsumer(rabbitmq_url=settings.rabbitmq_url)
    await consumer.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
