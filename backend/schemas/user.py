"""
Pydantic схемы для User.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    """Базовая схема User."""
    telegram_id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    language_code: str = "ru"


class UserCreate(UserBase):
    """Схема для создания пользователя."""
    pass


class UserResponse(UserBase):
    """Схема ответа пользователя."""
    id: UUID
    is_banned: bool = False
    last_active_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
