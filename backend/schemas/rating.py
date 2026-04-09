"""
Pydantic схемы для Rating.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RatingResponse(BaseModel):
    """Схема ответа рейтинга пользователя."""
    model_config = ConfigDict(from_attributes=True)

    primary_score: float
    behavioral_score: float
    total_score: float
    tier: Optional[str] = None
    percentile: Optional[float] = None
    rank_position: Optional[int] = None
    calculated_at: Optional[datetime] = None
