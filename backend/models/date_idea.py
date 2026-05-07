"""
Модель идеи для свидания (DateIdea).
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class DateIdea(Base):
    """Каталог идей для свиданий."""

    __tablename__ = "date_ideas"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    category: Mapped[str] = mapped_column(
        Enum(
            "cafe",
            "activity",
            "outdoor",
            "cultural",
            "entertainment",
            name="date_category_enum",
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avg_cost: Mapped[Optional[str]] = mapped_column(
        Enum("free", "low", "medium", "high", name="cost_level_enum", create_type=False),
        nullable=True,
    )
    suitable_interests: Mapped[List[str]] = mapped_column(JSONB, default=list)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    suggested_count: Mapped[int] = mapped_column(Integer, default=0)
    positive_feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<DateIdea(id={self.id}, category={self.category}, title={self.title})>"
