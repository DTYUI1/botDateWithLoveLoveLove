"""
Модель фотографии (Photo).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Photo(Base):
    """Метаданные фотографий профилей."""

    __tablename__ = "photos"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False, index=True
    )
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    s3_bucket: Mapped[str] = mapped_column(String(100), default="profile-photos")
    thumbnail_s3_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(50), default="image/jpeg")
    width: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    moderation_status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected", "under_review", name="moderation_status_enum", create_type=False),
        default="pending",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    profile = relationship("Profile", back_populates="photos", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Photo(id={self.id}, profile_id={self.profile_id}, s3_key={self.s3_key})>"
