"""
Telegram Bot Service для ConnectMe.
"""

import asyncio
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession
from loguru import logger

from config import settings
from api_client import APIClient
from middlewares.auth import AuthMiddleware

# Импорт роутеров
from handlers.start import router as start_router
from handlers.profile import router as profile_router
from handlers.search import router as search_router
from handlers.matches import router as matches_router
from handlers.rating import router as rating_router
from handlers.settings import router as settings_router
from handlers.photos import router as photos_router
from handlers.common import router as common_router, fallback_router


def setup_logging():
    """Настройка логирования."""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level,
    )
    logger.add(
        "logs/bot_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level="DEBUG",
        encoding="utf-8",
    )


async def on_startup(bot: Bot, api_client: APIClient):
    """Действия при запуске бота."""
    # Проверяем доступность backend
    health = await api_client.health_check()
    if health:
        logger.info("Backend API доступен")
    else:
        logger.warning("Backend API недоступен! Бот будет работать в ограниченном режиме.")

    # Устанавливаем команды бота
    await bot.set_my_commands([
        {"command": "start", "description": "Начать работу с ботом, регистрация"},
        {"command": "profile", "description": "Просмотр и редактирование своего профиля"},
        {"command": "search", "description": "Начать поиск анкет"},
        {"command": "matches", "description": "Просмотр списка мэтчей"},
        {"command": "rating", "description": "Узнать свой рейтинг"},
        {"command": "settings", "description": "Настройки предпочтений и уведомления"},
        {"command": "cancel", "description": "Отменить текущий диалог"},
    ])
    logger.info("Команды бота установлены")

    logger.info(f"Бот @{(await bot.me()).username} запущен")


async def on_shutdown(api_client: APIClient):
    """Действия при остановке бота."""
    await api_client.close()
    logger.info("Бот остановлен")


async def main():
    """Точка входа."""
    setup_logging()
    logger.info("Запуск ConnectMe Bot...")

    # Создаём API-клиент
    api_client = APIClient()

    # Создаём кастомную сессию с поддержкой HTTP прокси
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")

    if proxy_url:
        logger.info(f"Прокси для Telegram API: {proxy_url}")

    # Стандартная сессия с прокси — aiohttp корректно работает с Telegram
    from aiogram.client.session.aiohttp import AiohttpSession
    session = AiohttpSession(proxy=proxy_url)

    # Создаём бота и диспетчер
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Регистрируем API-клиент в диспетчере
    dp["api_client"] = api_client

    # Подключаем middleware
    dp.update.middleware(AuthMiddleware(api_client))

    # Подключаем роутеры
    dp.include_router(common_router)  # /cancel — должен быть первым
    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(photos_router)
    dp.include_router(search_router)
    dp.include_router(matches_router)
    dp.include_router(rating_router)
    dp.include_router(settings_router)
    dp.include_router(fallback_router)

    # Регистрируем хуки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запускаем polling
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await on_shutdown(api_client)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
