"""Хелперы для контекстного логирования.

Использование:

    from core.logging_context import with_user, with_match

    log = with_user(telegram_id=42)
    log.info("свайп записан")
    # → ... свайп записан | user_id=42

    log = with_match(match_id=7, user_id=42)
    log.error("не удалось отправить уведомление")

Хелперы тонкие — это просто `logger.bind(...)`. Главное правило:
**в бизнес-логах всегда биндить идентификатор сущности**, чтобы по логу ошибки
можно было однозначно найти затронутого пользователя/мэтч/фото.
"""

from typing import Any

from loguru import logger


def with_user(*, telegram_id: int | None = None, user_id: int | None = None, **extra: Any):
    return logger.bind(telegram_id=telegram_id, user_id=user_id, **extra)


def with_match(*, match_id: int, user_id: int | None = None, **extra: Any):
    return logger.bind(match_id=match_id, user_id=user_id, **extra)


def with_photo(*, photo_id: int, user_id: int | None = None, **extra: Any):
    return logger.bind(photo_id=photo_id, user_id=user_id, **extra)


def with_profile(*, profile_id: int, telegram_id: int | None = None, **extra: Any):
    return logger.bind(profile_id=profile_id, telegram_id=telegram_id, **extra)
