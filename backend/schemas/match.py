"""
Pydantic схемы для Swipe и Match.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from schemas.profile import ProfileShort


class SwipeRequest(BaseModel):
    """Запрос на свайп."""
    profile_id: UUID
    action: str  # "like", "pass", "super_like"

    @classmethod
    def validate_action(cls, v):
        if v not in ("like", "pass", "super_like"):
            raise ValueError("Действие должно быть 'like', 'pass' или 'super_like'")
        return v


class SwipeResponse(BaseModel):
    """Ответ на свайп."""
    is_match: bool = False
    match_profile_name: Optional[str] = None
    match_id: Optional[UUID] = None


class MatchResponse(BaseModel):
    """Схема ответа мэтча."""
    id: UUID
    profile: ProfileShort
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
