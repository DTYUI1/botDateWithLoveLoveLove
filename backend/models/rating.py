"""
Модели рейтингов (Rating).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Numeric, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class RatingCombined(Base):
    """Комбинированный рейтинг пользователя."""

    __tablename__ = "ratings_combined"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, index=True
    )
    primary_score: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    primary_weight: Mapped[float] = mapped_column(Numeric(3, 2), default=0.40)
    behavioral_score: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    behavioral_weight: Mapped[float] = mapped_column(Numeric(3, 2), default=0.50)
    referral_bonus: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    referral_weight: Mapped[float] = mapped_column(Numeric(3, 2), default=0.10)
    total_score: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    rank_position: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    percentile: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    tier: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<RatingCombined(profile_id={self.profile_id}, total={self.total_score})>"
