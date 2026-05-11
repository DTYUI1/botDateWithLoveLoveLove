"""
Pydantic схемы для Settings.
"""

from typing import Optional

from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    """Схема ответа настроек пользователя."""
    age_range_min: int = 18
    age_range_max: int = 100
    distance_max_km: int = 100
    looking_for: Optional[str] = None
    city: Optional[str] = None


class SettingsUpdate(BaseModel):
    """Схема для обновления настроек."""
    age_range_min: Optional[int] = Field(None, ge=18, le=99)
    age_range_max: Optional[int] = Field(None, ge=19, le=100)
    distance_max_km: Optional[int] = Field(None, ge=1, le=500)
    looking_for: Optional[str] = None
    city: Optional[str] = None
