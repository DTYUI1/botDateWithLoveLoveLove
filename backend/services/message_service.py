"""
Сервис чата между мэтчами.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.match import Match
from models.message import Message
from models.profile import Profile
from models.user import User
from schemas.message import MessageCreate


class MessageService:
    """Бизнес-логика Messages API."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile_by_telegram_id(self, telegram_id: int) -> Optional[Profile]:
        """Найти профиль по Telegram ID."""
        result = await self.db.execute(
            select(Profile)
            .join(User, Profile.user_id == User.id)
            .where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_match_for_profile(self, match_id: UUID, profile_id: UUID) -> Optional[Match]:
        """Проверить, что активный мэтч принадлежит профилю."""
        result = await self.db.execute(
            select(Match).where(
                Match.id == match_id,
                Match.status == "active",
                or_(Match.profile1_id == profile_id, Match.profile2_id == profile_id),
            )
        )
        return result.scalar_one_or_none()

    async def list_messages(
        self,
        match_id: UUID,
        profile_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[Message], int]:
        """Получить историю сообщений по активному мэтчу."""
        match = await self.get_match_for_profile(match_id, profile_id)
        if not match:
            raise ValueError("Мэтч не найден")

        total_result = await self.db.execute(
            select(func.count(Message.id)).where(
                Message.match_id == match_id,
                Message.deleted_at.is_(None),
            )
        )
        total = total_result.scalar() or 0

        result = await self.db.execute(
            select(Message)
            .where(Message.match_id == match_id, Message.deleted_at.is_(None))
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all(), total

    async def send_message(
        self,
        match_id: UUID,
        sender_profile_id: UUID,
        data: MessageCreate,
    ) -> Message:
        """Сохранить сообщение и обновить metadata мэтча."""
        match = await self.get_match_for_profile(match_id, sender_profile_id)
        if not match:
            raise ValueError("Мэтч не найден")

        if not data.content and not data.media_urls:
            raise ValueError("Сообщение не может быть пустым")

        now = datetime.utcnow()
        message = Message(
            match_id=match.id,
            sender_id=sender_profile_id,
            content=data.content,
            message_type=data.message_type,
            media_urls=data.media_urls,
            is_delivered=True,
            delivered_at=now,
            reply_to_id=data.reply_to_id,
        )
        self.db.add(message)

        preview = data.content or ("Медиа" if data.media_urls else "")
        match.message_count = (match.message_count or 0) + 1
        match.last_message_at = now
        match.last_message_preview = preview[:100]
        match.updated_at = now

        await self.db.flush()
        await self.db.refresh(message)
        return message
