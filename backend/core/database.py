"""
Подключение к PostgreSQL через async SQLAlchemy.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

# Создаём async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Фабрика сессий
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Базовый класс для моделей."""
    pass


async def get_db() -> AsyncSession:
    """Dependency для получения сессии БД."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Инициализация БД (создание таблиц)."""
    async with engine.begin() as conn:
        # Импортируем модели, чтобы они были зарегистрированы
        import models.user  # noqa: F401
        import models.profile  # noqa: F401
        import models.photo  # noqa: F401
        import models.swipe  # noqa: F401
        import models.match  # noqa: F401
        import models.message  # noqa: F401
        import models.rating  # noqa: F401
        import models.date_idea  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Закрытие подключения к БД."""
    await engine.dispose()
