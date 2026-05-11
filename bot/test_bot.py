"""
Минимальный тестовый бот для проверки подключения к Telegram API через прокси.
"""
import asyncio
import sys
import os

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv
from loguru import logger

# Загрузка переменных окружения из .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Настройка логирования
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="DEBUG")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
PROXY_URL = os.environ.get("HTTP_PROXY", "http://127.0.0.1:7897")

if not BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не найден в .env!")
    sys.exit(1)

router = Router()
dp = Dispatcher()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Ответ на /start"""
    logger.info(f"📩 Получен /start от {message.from_user.first_name} (ID: {message.from_user.id})")
    text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"Я тестовый бот ConnectMe.\n"
        f"Мой ID: {message.bot.id}\n"
        f"Твой ID: {message.from_user.id}\n\n"
        f"Прокси работает! ✅"
    )
    logger.info("📤 Отправляю ответ...")
    await message.answer(text)
    logger.info("✅ Ответ отправлен")


@router.message(F.text)
async def echo_message(message: Message):
    """Эхо на любые текстовые сообщения"""
    logger.info(f"💬 Сообщение: {message.text}")
    await message.answer(f"Ты написал: {message.text}")


async def on_startup(bot: Bot):
    me = await bot.me()
    logger.info(f"🤖 Бот @{me.username} (ID: {me.id}) запущен!")


async def on_shutdown():
    logger.info("🛑 Бот остановлен")


async def main():
    logger.info("🚀 Запуск тестового бота...")

    # Создаём сессию с прокси — стандартный aiohttp подход
    session = AiohttpSession(proxy=PROXY_URL)
    
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher()
    
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    logger.info("✅ Всё настроено, запускаю polling...")
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("⌨️ Получен сигнал остановки")
    finally:
        await session.close()
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
