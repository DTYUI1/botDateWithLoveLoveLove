"""
Тесты PhotoService и MinIO-интеграции.

MinIO-клиент полностью замокирован; реального S3 не требуется.
"""

import pytest
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from services.photo_service import PhotoService
from tests.conftest import MockDBResult


@pytest.fixture
def photo_service(mock_db_session):
    return PhotoService(mock_db_session)


@pytest.mark.asyncio
async def test_validate_upload_rejects_bad_mime(photo_service, mock_db_session):
    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=0)
    mock_db_session.execute.return_value = count_result

    res = await photo_service.validate_upload(
        profile_id=str(uuid4()), filename="x.bmp",
        content_type="image/bmp", file_size=1024,
    )
    assert res["valid"] is False
    assert "Неподдерживаемый формат" in res["error"]


@pytest.mark.asyncio
async def test_validate_upload_rejects_oversized(photo_service, mock_db_session):
    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=0)
    mock_db_session.execute.return_value = count_result

    res = await photo_service.validate_upload(
        profile_id=str(uuid4()), filename="big.jpg",
        content_type="image/jpeg", file_size=20 * 1024 * 1024,
    )
    assert res["valid"] is False
    assert "слишком большой" in res["error"]


@pytest.mark.asyncio
async def test_validate_upload_enforces_six_photo_limit(photo_service, mock_db_session):
    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=6)
    mock_db_session.execute.return_value = count_result

    res = await photo_service.validate_upload(
        profile_id=str(uuid4()), filename="a.jpg",
        content_type="image/jpeg", file_size=1024,
    )
    assert res["valid"] is False
    assert "Максимум" in res["error"]


@pytest.mark.asyncio
async def test_validate_upload_accepts_valid(photo_service, mock_db_session):
    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=2)
    mock_db_session.execute.return_value = count_result

    res = await photo_service.validate_upload(
        profile_id=str(uuid4()), filename="ok.jpg",
        content_type="image/jpeg", file_size=512_000,
    )
    assert res["valid"] is True


def test_generate_s3_key_format(photo_service):
    pid = str(uuid4())
    key = photo_service.generate_s3_key(pid, "selfie.JPEG")
    assert key.startswith(f"{pid}/")
    assert key.endswith(".jpeg")


@pytest.mark.asyncio
async def test_upload_to_storage_calls_minio(photo_service):
    """upload_to_storage должен дернуть MinIOClient.upload_photo с правильным content-type."""
    fake_client = MagicMock()
    fake_client.upload_photo = AsyncMock(return_value="http://minio/profile-photos/key")

    with patch.object(photo_service, "get_storage_client", return_value=fake_client):
        url = await photo_service.upload_to_storage(
            file_content=b"\xff\xd8\xff\xe0fake-jpeg",
            s3_key="abc/key.jpg",
            content_type="image/jpeg",
        )

    assert url == "http://minio/profile-photos/key"
    fake_client.upload_photo.assert_awaited_once()
    args, kwargs = fake_client.upload_photo.call_args
    assert args[1] == "abc/key.jpg"
    assert kwargs.get("content_type") == "image/jpeg"


@pytest.mark.asyncio
async def test_delete_from_storage_calls_minio(photo_service):
    fake_client = MagicMock()
    fake_client.delete_photo = AsyncMock()
    with patch.object(photo_service, "get_storage_client", return_value=fake_client):
        await photo_service.delete_from_storage("k/x.jpg")
    fake_client.delete_photo.assert_awaited_once_with("k/x.jpg")


@pytest.mark.asyncio
async def test_delete_photo_marks_soft_deleted(photo_service, mock_db_session):
    photo = MagicMock()
    photo.id = uuid4()
    photo.profile_id = uuid4()
    photo.is_primary = False
    photo.deleted_at = None
    photo.s3_key = "k/x.jpg"

    mock_db_session.execute.return_value = MockDBResult([photo])
    result = await photo_service.delete_photo(str(photo.profile_id), str(photo.id))
    assert result is photo
    assert photo.deleted_at is not None
    mock_db_session.flush.assert_awaited()
