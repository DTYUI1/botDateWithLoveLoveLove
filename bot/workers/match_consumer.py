"""Consumer уведомлений о мэтчах в боте.

Слушает очередь `match_notifications` и шлёт обоим участникам мэтча
push в Telegram.

Запуск:

    cd bot && python -m workers.match_consumer
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession
from loguru import logger

# Делает импорт `config`/`api_client` доступным когда запускаемся как
# `python -m workers.match_consumer` (cwd=bot/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402
from api_client import APIClient  # noqa: E402
from metrics import BOT_PUSH_DELIVERED_TOTAL, BOT_PUSH_FAILED_TOTAL  # noqa: E402
from workers.base_consumer import BaseConsumer  # noqa: E402


MATCH_PUSH_TEMPLATE = (
    "💖 У вас новый мэтч!\n"
    "Откройте /matches, чтобы увидеть подробности."
)


class MatchConsumer(BaseConsumer):
    queue_name = "match_notifications"

    def __init__(self, rabbitmq_url: str, bot: Bot, api: APIClient):
        super().__init__(rabbitmq_url)
        self.bot = bot
        self.api = api

    async def handle(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> None:
        match_id = payload.get("match_id")
        user1 = payload.get("user1_id")
        user2 = payload.get("user2_id")
        log = logger.bind(match_id=match_id, user1_id=user1, user2_id=user2)

        if not (user1 and user2):
            log.warning("[MatchConsumer] нет user1_id/user2_id")
            return

        for profile_id in (user1, user2):
            tg_id = await self._lookup_telegram_id(profile_id)
            if not tg_id:
                log.warning(f"[MatchConsumer] не нашли telegram_id для profile={profile_id}")
                continue
            try:
                await self.bot.send_message(tg_id, MATCH_PUSH_TEMPLATE)
                BOT_PUSH_DELIVERED_TOTAL.inc()
                log.bind(telegram_id=tg_id).info("[MatchConsumer] push отправлен")
            except Exception as e:
                BOT_PUSH_FAILED_TOTAL.inc()
                log.bind(telegram_id=tg_id).warning(
                    f"[MatchConsumer] не удалось отправить push: {type(e).__name__}: {e}"
                )
                raise

    async def _lookup_telegram_id(self, profile_id: Any) -> int | None:
        """Получить telegram_id профиля через backend API.

        Простейший вариант — отдельный endpoint `/profile/{id}/telegram_id`.
        Если такого нет (PR ещё не влит) — возвращаем None и логируем warning.
        """
        try:
            client = await self.api.get_client()
            resp = await client.get(f"/api/v1/profile/{profile_id}/telegram_id")
            if resp.status_code == 200:
                return int(resp.json().get("telegram_id"))
        except Exception as e:
            logger.warning(f"[MatchConsumer] lookup telegram_id упал: {e}")
        return None


async def main() -> None:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=AiohttpSession(proxy=proxy),
    )
    api = APIClient()
    try:
        consumer = MatchConsumer(settings.rabbitmq_url, bot=bot, api=api)
        await consumer.run_forever()
    finally:
        await api.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
