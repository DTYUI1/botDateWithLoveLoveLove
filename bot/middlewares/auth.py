"""
Middleware для авторизации пользователей по Telegram ID.
"""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from loguru import logger

from api_client import APIClient
from metrics import BOT_MESSAGES_TOTAL, BOT_CALLBACKS_TOTAL, BOT_FSM_STATE_TOTAL


class AuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки авторизации пользователя.
    
    При каждом обновлении:
    1. Проверяет, существует ли пользователь в базе
    2. Если нет — создаёт запись пользователя
    3. Добавляет user_id в middleware_data
    """

    def __init__(self, api_client: APIClient):
        self.api_client = api_client
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем пользователя из обновления
        update = event
        if isinstance(update, Update):
            # Извлекаем пользователя из разных типов обновлений
            user = None
            for attr in ('message', 'callback_query', 'inline_query', 'my_chat_member'):
                if hasattr(update, attr) and getattr(update, attr):
                    obj = getattr(update, attr)
                    if hasattr(obj, 'from_user'):
                        user = obj.from_user
                        BOT_MESSAGES_TOTAL.labels(kind=attr).inc()
                        if attr == 'callback_query':
                            BOT_CALLBACKS_TOTAL.inc()
                        break
                    elif hasattr(obj, 'from'):
                        user = obj.from_user
                        BOT_MESSAGES_TOTAL.labels(kind=attr).inc()
                        break
        else:
            user = getattr(event, 'from_user', None)

        if user:
            data['telegram_user'] = user
            log = logger.bind(telegram_id=user.id)
            log.debug(f"[Auth] Пользователь {user.first_name}")
            try:
                db_user = await self.api_client.get_or_create_user(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    language_code=user.language_code,
                )
                data['user'] = db_user
                log.info("[Auth] ✅ авторизован")
            except Exception as e:
                log.warning(f"[Auth] ОШИБКА авторизации: {type(e).__name__}: {e}")
                data['user'] = None
        else:
            logger.debug("[Auth] Пользователь не найден в обновлении")

        result = await handler(event, data)
        state = data.get("state")
        if state is not None:
            try:
                current_state = await state.get_state()
                if current_state:
                    BOT_FSM_STATE_TOTAL.labels(state=current_state).inc()
            except Exception as e:
                logger.debug(f"[Auth] FSM metric skipped: {type(e).__name__}: {e}")
        return result
