"""
Pydantic схемы для Date Ideas API.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DateIdeaCreate(BaseModel):
    """Создание идеи для свидания."""

    category: str = Field(..., pattern="^(cafe|activity|outdoor|cultural|entertainment)$")
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    avg_cost: Optional[str] = Field(None, pattern="^(free|low|medium|high)$")
    suitable_interests: List[str] = Field(default_factory=list)
    city: Optional[str] = Field(None, max_length=100)
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class DateIdeaResponse(BaseModel):
    """Ответ с идеей для свидания."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    title: str
    description: Optional[str] = None
    avg_cost: Optional[str] = None
    suitable_interests: List[str] = Field(default_factory=list)
    city: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    suggested_count: int = 0
    positive_feedback_count: int = 0
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class DateIdeaFeedback(BaseModel):
    """Обратная связь по идее."""

    positive: bool = True
