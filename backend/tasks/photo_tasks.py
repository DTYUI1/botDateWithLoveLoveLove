"""Celery tasks для обработки фотографий.

`process_photo` — асинхронная валидация и подготовка превью после
загрузки. На горячем пути API возвращает 200 сразу, а тяжёлая работа
(скачать из MinIO → проверить → сгенерировать превью → обновить статус)
уходит в worker.
"""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Any

from loguru import logger
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select

from celery_app import celery_app
from core.database import async_session_factory
from core.minio import init_minio_client
from models.photo import Photo


async def _process_one(photo_id: Any) -> dict:
    minio = init_minio_client()
    async with async_session_factory() as session:
        result = await session.execute(select(Photo).where(Photo.id == photo_id))
        photo = result.scalar_one_or_none()
        if photo is None:
            logger.bind(photo_id=str(photo_id)).warning(
                "[Celery photo] фото не найдено"
            )
            return {"status": "not_found", "photo_id": str(photo_id)}

        log = logger.bind(photo_id=str(photo.id), s3_key=photo.s3_key)
        try:
            data = await minio.get_photo_bytes(photo.s3_key)
            log.info(f"[Celery photo] скачано {len(data)} байт")
        except Exception as e:
            log.warning(f"[Celery photo] не удалось прочитать из MinIO: {e}")
            return {"status": "minio_error", "photo_id": str(photo.id)}

        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.thumbnail((512, 512))
                preview = BytesIO()
                image.convert("RGB").save(preview, format="JPEG", quality=85)
                preview.seek(0)
        except (UnidentifiedImageError, OSError, ValueError) as e:
            photo.moderation_status = "rejected"
            await session.commit()
            log.warning(f"[Celery photo] изображение не прошло валидацию: {e}")
            return {"status": "invalid_image", "photo_id": str(photo.id)}

        thumbnail_key = f"thumbnails/{photo.s3_key.rsplit('.', 1)[0]}.jpg"
        await minio.upload_photo(
            preview,
            thumbnail_key,
            content_type="image/jpeg",
        )
        photo.thumbnail_s3_key = thumbnail_key
        photo.moderation_status = "approved"
        await session.commit()

        log.info(f"[Celery photo] preview готов: {thumbnail_key}")
        return {
            "status": "ok",
            "photo_id": str(photo.id),
            "size": len(data),
            "thumbnail_s3_key": thumbnail_key,
        }


@celery_app.task(name="backend.process_photo")
def process_photo(photo_id: Any) -> dict:
    return asyncio.run(_process_one(photo_id))
