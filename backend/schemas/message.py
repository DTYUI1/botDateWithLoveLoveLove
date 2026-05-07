"""
Pydantic схемы для Messages API.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageCreate(BaseModel):
    """Запрос на отправку сообщения."""

    content: Optional[str] = Field(None, max_length=4000)
    message_type: str = Field("text", pattern="^(text|photo|system)$")
    media_urls: List[str] = Field(default_factory=list)
    reply_to_id: Optional[UUID] = None

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value):
        if value is None:
            return value
        value = value.strip()
        return value or None

    @field_validator("media_urls")
    @classmethod
    def validate_media_urls(cls, value):
        if len(value) > 10:
            raise ValueError("Можно приложить не больше 10 медиа")
        return value


class MessageResponse(BaseModel):
    """Ответ с сообщением."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    match_id: UUID
    sender_id: UUID
    content: Optional[str] = None
    message_type: str
    media_urls: List[str] = Field(default_factory=list)
    is_read: bool
    read_at: Optional[datetime] = None
    is_delivered: bool
    delivered_at: Optional[datetime] = None
    reply_to_id: Optional[UUID] = None
    is_edited: bool
    edited_at: Optional[datetime] = None
    created_at: datetime


class MessageListResponse(BaseModel):
    """Пагинированный ответ истории сообщений."""

    messages: List[MessageResponse]
    limit: int
    offset: int
    total: int
