"""
Pydantic схемы для Swipe и Match.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from schemas.profile import ProfileShort


class SwipeRequest(BaseModel):
    """Запрос на свайп."""
    profile_id: UUID
    action: str  # "like", "pass", "super_like"


class SwipeResponse(BaseModel):
    """Ответ на свайп."""
    is_match: bool = False
    match_profile_name: Optional[str] = None
    match_username: Optional[str] = None
    match_id: Optional[UUID] = None


class MatchResponse(BaseModel):
    """Схема ответа мэтча."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile: ProfileShort
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: datetime
