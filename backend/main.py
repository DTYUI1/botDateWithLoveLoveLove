"""
ConnectMe Backend API — FastAPI приложение.
"""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from core.config import settings
from core.database import init_db, close_db
from core.redis_client import get_redis_client, close_redis_client

# Импорт роутеров
from api.v1.auth import router as auth_router
from api.v1.profile import router as profile_router
from api.v1.matching import router as matching_router
from api.v1.rating import router as rating_router
from api.v1.settings import router as settings_router
from api.v1.photos import router as photos_router
from api.v1.health import router as health_router


def setup_logging():
    """Настройка логирования."""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level,
    )
    logger.add(
        "logs/backend_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level="DEBUG",
        encoding="utf-8",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle приложения: startup и shutdown."""
    # Startup
    logger.info("Запуск ConnectMe Backend API...")
    
    # Инициализация БД
    try:
        await init_db()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ ОШИБКА инициализации БД: {type(e).__name__}: {e}")
        logger.warning("⚠️ Продолжение без БД (сервис запущен, но API может не работать)")
    
    # Инициализация Redis (полностью optional)
    try:
        redis_client = await get_redis_client()
        is_connected = await redis_client.health_check()
        if is_connected:
            logger.info("✅ Redis подключен")
        else:
            logger.warning("⚠️ Redis не отвечает, продолжение без кэширования")
    except Exception as e:
        logger.warning(f"⚠️ Redis недоступен: {type(e).__name__}: {e}")
        logger.warning("⚠️ Продолжение без кэширования (matching будет работать без Redis)")
    
    yield
    
    # Shutdown
    try:
        await close_redis_client()
        logger.info("✅ Redis отключен")
    except Exception:
        pass
    
    try:
        await close_db()
        logger.info("✅ БД отключена")
    except Exception:
        pass
    
    logger.info("✅ Backend API остановлен")


# Создание приложения
app = FastAPI(
    title="ConnectMe API",
    description="Backend API для Telegram Dating бота ConnectMe",
    version="1.0.0",
    lifespan=lifespan,
)

# Подключение роутеров
app.include_router(auth_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")
app.include_router(matching_router, prefix="/api/v1")
app.include_router(rating_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(photos_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Корень API."""
    return {
        "service": "ConnectMe API",
        "version": "1.0.0",
        "docs": "/docs",
    }
