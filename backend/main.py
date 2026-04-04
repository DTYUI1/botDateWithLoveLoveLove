"""
ConnectMe Backend API — FastAPI приложение.
"""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from core.config import settings
from core.database import init_db, close_db

# Импорт роутеров
from api.v1.auth import router as auth_router
from api.v1.profile import router as profile_router
from api.v1.matching import router as matching_router
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
    await init_db()
    logger.info("База данных инициализирована")
    yield
    # Shutdown
    await close_db()
    logger.info("Backend API остановлен")


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
app.include_router(health_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Корень API."""
    return {
        "service": "ConnectMe API",
        "version": "1.0.0",
        "docs": "/docs",
    }
