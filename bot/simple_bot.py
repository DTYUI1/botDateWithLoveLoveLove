"""
ConnectMe Bot — простая версия. Без backend, без middleware.
Отвечает на /start и базовые команды.
"""
import asyncio
import sys
import os

# Загрузка переменных окружения из .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from loguru import logger

# Настройка логирования
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")
logger.add("logs/bot_{time:YYYY-MM-DD}.log", rotation="00:00", retention="7 days", level="DEBUG")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
PROXY_URL = os.environ.get("HTTP_PROXY", "http://127.0.0.1:7897")

if not BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не найден в .env!")
    sys.exit(1)

router = Router()

# Простое хранилище пользователей
users_db = {}


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Ответ на /start"""
    tid = message.from_user.id
    name = message.from_user.first_name
    
    if tid not in users_db:
        users_db[tid] = {"name": name, "registered": True}
        text = (
            f"💕 Добро пожаловать в ConnectMe, {name}!\n\n"
            f"Я помогу тебе найти интересного собеседника.\n"
            f"Ты зарегистрирован! ✅\n\n"
            f"Используй:\n"
            f"/profile — посмотреть профиль\n"
            f"/search — поиск анкет\n"
            f"/settings — настройки"
        )
        await message.answer(text)
        logger.info(f"✅ Новый пользователь {name} (ID: {tid}) зарегистрирован")
    else:
        text = (
            f"👋 Привет, {name}! Рада видеть тебя снова!\n\n"
            f"Что хочешь сделать?"
        )
        await message.answer(text)
        logger.info(f"🔄 Вернувшийся пользователь {name} (ID: {tid})")


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    tid = message.from_user.id
    if tid in users_db:
        u = users_db[tid]
        await message.answer(f"📋 Твой профиль:\nИмя: {u['name']}\nTelegram ID: {tid}")
    else:
        await message.answer("⚠️ Сначала нажми /start")


@router.message(Command("search"))
async def cmd_search(message: Message):
    await message.answer("🔍 Поиск анкет скоро будет доступен! Пока анкет нет.")


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    await message.answer("⚙️ Настройки скоро будут доступны!")


@router.message(F.text)
async def echo_all(message: Message):
    await message.answer(f"💬 Написано: \"{message.text}\"\n\nИспользуй /start для начала работы")


async def on_startup(bot: Bot):
    me = await bot.me()
    logger.info(f"🤖 @{me.username} запущен!")


async def main():
    logger.info("🚀 ConnectMe Bot v2 (simple)...")
    
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.include_router(router)
    dp.startup.register(on_startup)
    
    logger.info("✅ Polling...")
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("⌨️ Остановлен")
    finally:
        await session.close()
        logger.info("🛑 Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
