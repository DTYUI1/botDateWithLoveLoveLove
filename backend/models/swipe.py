"""
Модель свайпа (Swipe).
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from core.database import Base


class Swipe(Base):
    """История действий пользователей (лайки/пропуски)."""

    __tablename__ = "swipes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    swiper_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    swiped_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(
        Enum("like", "pass", "super_like", name="swipe_action_enum", create_type=False),
        nullable=False,
    )
    source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    time_spent_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    context_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Swipe(id={self.id}, swiper={self.swiper_id}, target={self.swiped_id}, action={self.action})>"
