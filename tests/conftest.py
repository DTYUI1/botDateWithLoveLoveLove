"""
Conftest для тестирования Backend API ConnectMe.

Предоставляет fixtures для:
- Тестового FastAPI приложения
- Тестовой БД (SQLite для юнит-тестов)
- HTTP клиента (httpx.AsyncClient)
- Тестовых данных пользователей и профилей
"""

import os
import sys
import pytest
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Добавляем backend в path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


@pytest.fixture(scope="session")
def event_loop():
    """Создаёт event loop для всех тестов."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session():
    """
    Создаёт мокированную сессию БД для юнит-тестов сервисов.
    
    Не требует реальной БД — все вызовы мокируются.
    """
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def test_user_data():
    """Базовые данные тестового пользователя."""
    return {
        "telegram_id": 123456789,
        "username": "test_user",
        "first_name": "Тест",
        "last_name": "Пользователь",
        "language_code": "ru",
    }


@pytest.fixture
def test_profile_data():
    """Базовые данные тестового профиля."""
    return {
        "display_name": "Тестовый Пользователь",
        "age": 25,
        "gender": "male",
        "bio": "Люблю программирование и путешествия. Ищу интересного собеседника.",
        "interests": ["программирование", "музыка", "путешествия", "кино"],
        "city": "Москва",
        "looking_for": "female",
    }


@pytest.fixture
def test_profile_data_2():
    """Данные второго тестового профиля (для тестирования matching)."""
    return {
        "display_name": "Анна",
        "age": 23,
        "gender": "female",
        "bio": "Фотограф и путешественница. Люблю природу и искусство.",
        "interests": ["фотография", "путешествия", "искусство", "йога"],
        "city": "Москва",
        "looking_for": "male",
    }


class MockDBResult:
    """Мокированный результат SQLAlchemy query."""
    
    def __init__(self, data=None):
        self._data = data
    
    def scalar_one_or_none(self):
        if isinstance(self._data, list) and len(self._data) > 0:
            return self._data[0]
        return self._data
    
    def scalars(self):
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=self._data or [])
        return mock_scalars
    
    def all(self):
        return self._data or []


@pytest.fixture
def mock_db_with_user(test_user_data, mock_db_session):
    """Настраивает мок БД с существующим пользователем."""
    from models.user import User
    
    user = User(**test_user_data)
    user.id = "550e8400-e29b-41d4-a716-446655440000"
    
    mock_db_session.execute.return_value = MockDBResult([user])
    return mock_db_session, user


@pytest.fixture
async def api_client():
    """
    Создаёт httpx.AsyncClient для тестирования API endpoints.
    
    Использует тестовый транспорт (без реального сервера).
    Для integration тестов нужен запущенный сервер.
    """
    from backend.main import app
    
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
