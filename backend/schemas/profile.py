"""
Pydantic схемы для Profile.
"""

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict


class ProfileBase(BaseModel):
    """Базовая схема Profile."""
    display_name: Optional[str] = Field(None, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None  # male, female, other
    bio: Optional[str] = Field(None, max_length=500)
    interests: List[str] = Field(default_factory=list)
    city: Optional[str] = None
    looking_for: Optional[str] = None  # male, female, both


class ProfileCreate(ProfileBase):
    """Схема для создания профиля."""
    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    age: Optional[int] = Field(None, ge=18, le=99)

    @field_validator("age")
    @classmethod
    def validate_age(cls, v):
        if v is not None and (v < 18 or v > 99):
            raise ValueError("Возраст должен быть от 18 до 99 лет")
        return v


class ProfileUpdate(BaseModel):
    """Схема для обновления профиля."""
    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    interests: Optional[List[str]] = None
    city: Optional[str] = None
    age_range_min: Optional[int] = Field(None, ge=18)
    age_range_max: Optional[int] = Field(None, le=100)
    distance_max_km: Optional[int] = Field(None, ge=1, le=500)
    looking_for: Optional[str] = None


class ProfileResponse(BaseModel):
    """Схема ответа профиля."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    display_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    bio: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    city: Optional[str] = None
    looking_for: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    profile_completion_pct: int = 0
    created_at: datetime
    updated_at: datetime


class ProfileShort(BaseModel):
    """Краткая схема профиля (для отображения в свайпах)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: Optional[str] = None
    age: Optional[int] = None
    city: Optional[str] = None
    bio: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
