"""
Сервис для работы с фотографиями профилей.

Реализует:
- Загрузку фото в MinIO
- Валидацию (макс 6 фото, формат, размер)
- Удаление фото
- Генерацию presigned URLs
"""

import uuid
from typing import Optional, List
from io import BytesIO

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from models.profile import Profile
from models.photo import Photo as PhotoModel
from core.config import settings


class PhotoService:
    """Сервис для управления фотографиями профиля."""

    MAX_PHOTOS_PER_PROFILE = 6
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_photo_count(self, profile_id: str) -> int:
        """Получить количество активных фото у профиля."""
        result = await self.db.execute(
            select(func.count(PhotoModel.id)).where(
                and_(
                    PhotoModel.profile_id == profile_id,
                    PhotoModel.deleted_at.is_(None),
                )
            )
        )
        return result.scalar() or 0

    async def validate_upload(
        self,
        profile_id: str,
        filename: str,
        content_type: str,
        file_size: int,
    ) -> dict:
        """
        Валидировать фото перед загрузкой.
        
        Returns:
            Dict с результатом валидации: {"valid": bool, "error": str|None}
        """
        # Проверка типа файла
        if content_type not in self.ALLOWED_MIME_TYPES:
            return {
                "valid": False,
                "error": f"Неподдерживаемый формат: {content_type}. Разрешены: JPEG, PNG, WebP, GIF",
            }
        
        # Проверка размера
        if file_size > self.MAX_FILE_SIZE:
            return {
                "valid": False,
                "error": f"Файл слишком большой: {file_size / 1024 / 1024:.1f} МБ (макс 10 МБ)",
            }
        
        # Проверка количества фото
        current_count = await self.get_photo_count(profile_id)
        if current_count >= self.MAX_PHOTOS_PER_PROFILE:
            return {
                "valid": False,
                "error": f"Максимум {self.MAX_PHOTOS_PER_PROFILE} фото на профиль. Удалите старые фото.",
            }
        
        return {"valid": True, "error": None}

    def generate_s3_key(self, profile_id: str, filename: str) -> str:
        """
        Сгенерировать уникальное имя файла для S3.
        
        Format: profile-photos/{profile_id}/{uuid}_{original_name}
        """
        unique_id = uuid.uuid4().hex[:12]
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "jpg"
        return f"profile-photos/{profile_id}/{unique_id}.{ext}"

    async def create_photo_record(
        self,
        profile_id: str,
        s3_key: str,
        filename: str,
        content_type: str,
        file_size: int,
        is_primary: bool = False,
    ) -> PhotoModel:
        """Создать запись о фото в БД."""
        # Если это первое фото, делаем его primary
        if not is_primary:
            current_count = await self.get_photo_count(profile_id)
            is_primary = current_count == 0
        
        photo = PhotoModel(
            profile_id=profile_id,
            s3_key=s3_key,
            mime_type=content_type,
            file_size_bytes=file_size,
            is_primary=is_primary,
            sort_order=await self.get_photo_count(profile_id),
        )
        self.db.add(photo)
        await self.db.flush()
        
        logger.info(f"[PhotoService] Фото создано: {s3_key}, primary={is_primary}")
        return photo

    async def delete_photo(
        self,
        profile_id: str,
        photo_id: str,
    ) -> Optional[PhotoModel]:
        """
        Мягко удалить фото (пометить как удалённое).
        
        Returns:
            PhotoModel или None
        """
        from datetime import datetime
        
        result = await self.db.execute(
            select(PhotoModel).where(
                and_(
                    PhotoModel.id == photo_id,
                    PhotoModel.profile_id == profile_id,
                    PhotoModel.deleted_at.is_(None),
                )
            )
        )
        photo = result.scalar_one_or_none()
        
        if not photo:
            return None
        
        # Мягкое удаление
        photo.deleted_at = datetime.utcnow()
        
        # Если было primary, назначаем новое primary
        if photo.is_primary:
            await self._assign_new_primary(profile_id, exclude_photo_id=photo_id)
        
        await self.db.flush()
        logger.info(f"[PhotoService] Фото удалено: {photo_id}")
        return photo

    async def set_primary_photo(
        self,
        profile_id: str,
        photo_id: str,
    ) -> bool:
        """Назначить фото основным."""
        result = await self.db.execute(
            select(PhotoModel).where(
                and_(
                    PhotoModel.id == photo_id,
                    PhotoModel.profile_id == profile_id,
                    PhotoModel.deleted_at.is_(None),
                )
            )
        )
        photo = result.scalar_one_or_none()
        
        if not photo:
            return False
        
        # Снимаем primary со всех фото
        await self._clear_all_primary(profile_id)
        
        # Назначаем новое primary
        photo.is_primary = True
        await self.db.flush()
        return True

    async def get_profile_photos(
        self,
        profile_id: str,
    ) -> List[PhotoModel]:
        """Получить все активные фото профиля."""
        result = await self.db.execute(
            select(PhotoModel)
            .where(
                and_(
                    PhotoModel.profile_id == profile_id,
                    PhotoModel.deleted_at.is_(None),
                )
            )
            .order_by(PhotoModel.sort_order)
        )
        return result.scalars().all()

    # ============================================
    # Helpers
    # ============================================

    async def _assign_new_primary(self, profile_id: str, exclude_photo_id: str = None):
        """Назначить новое primary фото."""
        query = select(PhotoModel).where(
            and_(
                PhotoModel.profile_id == profile_id,
                PhotoModel.deleted_at.is_(None),
                PhotoModel.id != exclude_photo_id if exclude_photo_id else True,
            )
        ).limit(1)
        
        result = await self.db.execute(query)
        photo = result.scalar_one_or_none()
        
        if photo:
            photo.is_primary = True

    async def _clear_all_primary(self, profile_id: str):
        """Снять primary со всех фото."""
        from sqlalchemy import update
        
        stmt = (
            update(PhotoModel)
            .where(
                and_(
                    PhotoModel.profile_id == profile_id,
                    PhotoModel.deleted_at.is_(None),
                )
            )
            .values(is_primary=False)
        )
        await self.db.execute(stmt)
