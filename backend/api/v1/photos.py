"""
API роутер для работы с фотографиями профиля.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from loguru import logger

from models.photo import Photo as PhotoModel

from core.database import get_db
from models.user import User
from models.profile import Profile
from services.photo_service import PhotoService

router = APIRouter(prefix="/profile/photo", tags=["photos"])


@router.post("", response_model=dict)
async def upload_photo(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Загрузить фотографию профиля.
    
    Ограничения:
    - Максимум 6 фото на профиль
    - Форматы: JPEG, PNG, WebP, GIF
    - Максимальный размер: 10 МБ
    
    Returns:
        - photo_id: ID записи в БД
        - s3_key: Ключ в MinIO
        - is_primary: Является ли основным фото
    """
    logger.info(f"[Backend Photo] POST /profile/photo telegram_id={telegram_id}")
    
    try:
        # Находим профиль пользователя
        user_result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        profile_result = await db.execute(
            select(Profile).where(Profile.user_id == user.id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден. Создайте анкету.")
        
        # Проверяем тип файла
        content_type = file.content_type or "image/jpeg"
        filename = file.filename or "photo.jpg"
        
        # Читаем файл в память для валидации
        file_content = await file.read()
        file_size = len(file_content)
        
        # Валидация
        photo_service = PhotoService(db)
        validation = await photo_service.validate_upload(
            profile_id=str(profile.id),
            filename=filename,
            content_type=content_type,
            file_size=file_size,
        )
        
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=validation["error"])
        
        # Генерируем S3 ключ и загружаем объект в приватный bucket MinIO
        s3_key = photo_service.generate_s3_key(str(profile.id), filename)
        try:
            storage_url = await photo_service.upload_to_storage(
                file_content=file_content,
                s3_key=s3_key,
                content_type=content_type,
            )
        except Exception as e:
            logger.error(f"[Backend Photo] ОШИБКА MinIO upload: {type(e).__name__}: {e}")
            raise HTTPException(status_code=502, detail="Не удалось загрузить фото в хранилище")
        
        # Создаём запись в БД
        photo = await photo_service.create_photo_record(
            profile_id=str(profile.id),
            s3_key=s3_key,
            filename=filename,
            content_type=content_type,
            file_size=file_size,
        )
        
        await db.commit()

        # Celery: фоновая валидация/превью, не блокирует HTTP-ответ.
        try:
            from tasks.photo_tasks import process_photo
            process_photo.delay(photo_id=str(photo.id))
        except Exception as e:
            logger.warning(f"[Backend Photo] Celery process_photo не отправлена: {e}")

        return {
            "photo_id": str(photo.id),
            "s3_key": photo.s3_key,
            "s3_bucket": photo.s3_bucket,
            "storage_url": storage_url,
            "is_primary": photo.is_primary,
            "message": "Фото успешно загружено",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Backend Photo] ОШИБКА upload_photo: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось загрузить фото")


@router.get("", response_model=List[dict])
async def get_photos(
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """Получить все фото профиля."""
    logger.info(f"[Backend Photo] GET /profile/photo telegram_id={telegram_id}")
    
    try:
        user_result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        profile_result = await db.execute(
            select(Profile).where(Profile.user_id == user.id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        
        photo_service = PhotoService(db)
        photos = await photo_service.get_profile_photos(str(profile.id))
        
        result = []
        for photo in photos:
            result.append({
                "id": str(photo.id),
                "s3_key": photo.s3_key,
                "s3_bucket": photo.s3_bucket,
                "url": f"/api/v1/profile/photo/{photo.id}/raw",
                "is_primary": photo.is_primary,
                "mime_type": photo.mime_type,
                "file_size_bytes": photo.file_size_bytes,
                "created_at": photo.created_at.isoformat() if photo.created_at else None,
            })

        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Backend Photo] ОШИБКА get_photos: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось получить фото")


@router.get("/{photo_id}/raw")
async def get_photo_raw(
    photo_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Отдать байты фото напрямую (для bot, который проксирует фото в Telegram)."""
    result = await db.execute(
        select(PhotoModel).where(
            and_(
                PhotoModel.id == photo_id,
                PhotoModel.deleted_at.is_(None),
            )
        )
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    photo_service = PhotoService(db)
    try:
        data = await photo_service.get_photo_bytes(photo.s3_key)
    except Exception as e:
        logger.error(f"[Backend Photo] Не удалось получить байты {photo.s3_key}: {e}")
        raise HTTPException(status_code=502, detail="Не удалось получить фото")

    return Response(content=data, media_type=photo.mime_type or "image/jpeg")


@router.delete("/{photo_id}", response_model=dict)
async def delete_photo(
    photo_id: str,
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """Удалить фотографию профиля."""
    logger.info(f"[Backend Photo] DELETE /profile/photo/{photo_id} telegram_id={telegram_id}")
    
    try:
        user_result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        profile_result = await db.execute(
            select(Profile).where(Profile.user_id == user.id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        
        photo_service = PhotoService(db)
        photo = await photo_service.delete_photo(str(profile.id), photo_id)
        
        if not photo:
            raise HTTPException(status_code=404, detail="Фото не найдено")
        
        try:
            await photo_service.delete_from_storage(photo.s3_key)
        except Exception as e:
            logger.warning(f"[Backend Photo] Фото помечено удалённым, но MinIO delete не выполнен: {e}")

        await db.commit()
        
        return {"message": "Фото удалено"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Backend Photo] ОШИБКА delete_photo: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось удалить фото")


@router.post("/{photo_id}/set-primary", response_model=dict)
async def set_primary_photo(
    photo_id: str,
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """Назначить фото основным."""
    logger.info(f"[Backend Photo] POST /profile/photo/{photo_id}/set-primary telegram_id={telegram_id}")
    
    try:
        user_result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        profile_result = await db.execute(
            select(Profile).where(Profile.user_id == user.id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        
        photo_service = PhotoService(db)
        success = await photo_service.set_primary_photo(str(profile.id), photo_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Фото не найдено")
        
        await db.commit()
        
        return {"message": "Основное фото обновлено"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Backend Photo] ОШИБКА set_primary_photo: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить основное фото")
