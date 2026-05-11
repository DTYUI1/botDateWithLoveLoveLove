"""
Модель профиля (Profile).
"""

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Numeric, SmallInteger, String, Text, func, ForeignKey, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Profile(Base):
    """Расширенный профиль пользователя для знакомств."""

    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(
        Enum("male", "female", "other", name="gender_enum", create_type=False), nullable=True
    )
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    height_cm: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    interests: Mapped[List[str]] = mapped_column(JSONB, default=list)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    location_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    looking_for: Mapped[Optional[str]] = mapped_column(
        Enum("male", "female", "both", name="looking_for_enum", create_type=False), nullable=True
    )
    age_range_min: Mapped[int] = mapped_column(SmallInteger, default=18)
    age_range_max: Mapped[int] = mapped_column(SmallInteger, default=100)
    distance_max_km: Mapped[int] = mapped_column(SmallInteger, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_completion_pct: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="profile", lazy="selectin")
    photos = relationship("Photo", back_populates="profile", lazy="selectin")

    __table_args__ = (
        CheckConstraint("age_range_min >= 18", name="chk_age_min"),
        CheckConstraint("age_range_max <= 100", name="chk_age_max"),
        CheckConstraint("distance_max_km BETWEEN 1 AND 500", name="chk_distance"),
    )

    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, display_name={self.display_name}, city={self.city})>"
