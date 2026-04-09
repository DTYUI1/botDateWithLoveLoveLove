"""
API роутер для health check.
"""

from fastapi import APIRouter
from datetime import datetime
from loguru import logger

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Проверка работоспособности сервиса."""
    health_data = {
        "status": "ok",
        "service": "connectme-backend",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "api": "healthy",
        }
    }
    
    # Проверяем Redis
    try:
        from core.redis_client import get_redis_client
        redis_client = await get_redis_client()
        redis_ok = await redis_client.health_check()
        health_data["components"]["redis"] = "healthy" if redis_ok else "unhealthy"
        if not redis_ok:
            health_data["status"] = "degraded"
    except Exception as e:
        logger.warning(f"Health check Redis failed: {e}")
        health_data["components"]["redis"] = "unhealthy"
        health_data["status"] = "degraded"
    
    # Проверяем БД
    try:
        from sqlalchemy import text
        from core.database import get_db
        async for db in get_db():
            await db.execute(text("SELECT 1"))
            health_data["components"]["database"] = "healthy"
            break
    except Exception as e:
        logger.warning(f"Health check DB failed: {e}")
        health_data["components"]["database"] = "unhealthy"
        health_data["status"] = "degraded"
    
    return health_data
