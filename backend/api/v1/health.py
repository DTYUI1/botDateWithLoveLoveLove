"""
API роутер для health check.
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Проверка работоспособности сервиса."""
    return {
        "status": "ok",
        "service": "connectme-backend",
        "timestamp": datetime.utcnow().isoformat(),
    }
