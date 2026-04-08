"""
Клиент для работы с MinIO (S3-совместимое хранилище).

Реализует:
- Загрузку фото
- Получение presigned URL
- Удаление фото
- Валидацию файлов
"""

import io
from typing import BinaryIO, Optional
from datetime import timedelta

from minio import Minio
from minio.error import S3Error


class MinIOClient:
    """
    Клиент для работы с MinIO.
    
    Args:
        endpoint: URL MinIO сервера
        access_key: Access key
        secret_key: Secret key
        bucket_name: Name bucket
        secure: Использовать ли HTTPS
    """

    ALLOWED_CONTENT_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str = "profile-photos",
        secure: bool = False
    ):
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self.bucket_name = bucket_name
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Создать bucket если не существует."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error as e:
            raise Exception(f"Error creating bucket: {e}")

    def validate_file(self, file: BinaryIO, content_type: str) -> bool:
        """
        Валидировать файл перед загрузкой.
        
        Args:
            file: Файловый объект
            content_type: MIME тип
        """
        if content_type not in self.ALLOWED_CONTENT_TYPES:
            raise ValueError(f"Неподдерживаемый тип файла: {content_type}")

        # Проверить размер
        file.seek(0, io.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(f"Файл слишком большой: {file_size} bytes (max: {self.MAX_FILE_SIZE})")

        if file_size == 0:
            raise ValueError("Файл пустой")

        return True

    async def upload_photo(
        self,
        file: BinaryIO,
        object_name: str,
        content_type: str = "image/jpeg"
    ) -> str:
        """
        Загрузить фото в MinIO.
        
        Args:
            file: Файловый объект
            object_name: Имя объекта в bucket (например: user_123/photo_1.jpg)
            content_type: MIME тип файла
            
        Returns:
            URL загруженного файла
        """
        self.validate_file(file, content_type)

        try:
            # Получить размер файла
            file.seek(0, io.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            self.client.put_object(
                self.bucket_name,
                object_name,
                file,
                length=file_size,
                content_type=content_type
            )

            # Сгенерировать URL
            url = f"http://{self.client._base_url.netloc}/{self.bucket_name}/{object_name}"
            return url
        except S3Error as e:
            raise Exception(f"Failed to upload photo: {e}")

    async def get_presigned_url(
        self,
        object_name: str,
        expiry_seconds: int = 3600
    ) -> str:
        """
        Получить временный URL для доступа к фото.
        
        Args:
            object_name: Имя объекта в bucket
            expiry_seconds: Время действия URL
            
        Returns:
            Presigned URL
        """
        try:
            url = self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=timedelta(seconds=expiry_seconds)
            )
            return url
        except S3Error as e:
            raise Exception(f"Failed to generate URL: {e}")

    async def delete_photo(self, object_name: str):
        """
        Удалить фото из MinIO.
        
        Args:
            object_name: Имя объекта в bucket
        """
        try:
            self.client.remove_object(self.bucket_name, object_name)
        except S3Error as e:
            raise Exception(f"Failed to delete photo: {e}")

    async def photo_exists(self, object_name: str) -> bool:
        """Проверить существует ли фото."""
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False

    async def get_photo_info(self, object_name: str) -> dict:
        """Получить информацию о фото."""
        try:
            stat = self.client.stat_object(self.bucket_name, object_name)
            return {
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
            }
        except S3Error as e:
            raise Exception(f"Failed to get photo info: {e}")
