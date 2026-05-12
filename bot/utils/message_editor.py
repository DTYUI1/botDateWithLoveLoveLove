"""Утилиты для in-place обновления экранов бота.

Цель — избавиться от "ленты" новых сообщений в callback-навигации:
вместо `message.answer(...)` для каждого экрана используем редактирование
текущего сообщения и аккуратный fallback на ответ, если редактирование
невозможно (тип сообщения не совпадает, "message is not modified",
сообщение удалено и т.п.).
"""

from typing import Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)
from loguru import logger


def _has_media(message: Message) -> bool:
    return bool(
        message.photo
        or message.video
        or message.animation
        or message.document
    )


async def safe_delete(message: Optional[Message]) -> None:
    """Удалить сообщение, проглатывая любые ошибки Telegram API."""
    if message is None:
        return
    try:
        await message.delete()
    except Exception as exc:
        logger.debug(f"[message_editor] safe_delete failed: {exc}")


async def edit_or_answer(
    message: Message,
    text: str,
    *,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> Message:
    """Заменить содержимое бот-сообщения текстом.

    Контракт: показать чистый текстовый экран в этом чате. Если текущее
    сообщение содержит media (photo/video/animation/document), его
    `edit_caption` оставил бы картинку висеть под новым текстом, поэтому
    мы её удаляем и шлём новое сообщение.

    Алгоритм:
    1. media-сообщение → safe_delete + answer (НЕ edit_caption, иначе
       старая картинка "залипает" под новым текстом).
    2. text-сообщение → edit_text.
    3. "message is not modified" → синхронизируем reply_markup и
       возвращаем исходное сообщение.
    4. Любые другие ошибки → fallback safe_delete + answer.
    """
    if _has_media(message):
        await safe_delete(message)
        return await message.answer(text, reply_markup=reply_markup)

    try:
        return await message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        err = str(exc).lower()
        if "message is not modified" in err:
            try:
                await message.edit_reply_markup(reply_markup=reply_markup)
            except Exception as inner:
                logger.debug(f"[message_editor] markup sync failed: {inner}")
            return message
        logger.debug(f"[message_editor] edit fallback to answer: {exc}")
    except Exception as exc:
        logger.debug(f"[message_editor] edit unexpected fallback: {exc}")

    await safe_delete(message)
    return await message.answer(text, reply_markup=reply_markup)


async def replace_with_photo(
    message: Message,
    *,
    photo_bytes: bytes,
    caption: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    filename: str = "photo.jpg",
) -> Message:
    """Заменить экран на photo+caption.

    Если текущее сообщение уже содержит media — пробуем edit_media,
    иначе удаляем старое и отправляем новый photo-message.
    """
    if _has_media(message):
        try:
            return await message.edit_media(
                media=InputMediaPhoto(
                    media=BufferedInputFile(photo_bytes, filename=filename),
                    caption=caption,
                ),
                reply_markup=reply_markup,
            )
        except Exception as exc:
            logger.debug(f"[message_editor] edit_media fallback: {exc}")

    await safe_delete(message)
    return await message.answer_photo(
        photo=BufferedInputFile(photo_bytes, filename=filename),
        caption=caption,
        reply_markup=reply_markup,
    )


async def answer_temp(message: Message, text: str) -> Message:
    """Отправить временное статус-сообщение.

    Вызывающая сторона должна впоследствии заменить/удалить его
    через `edit_or_answer` или `safe_delete`.
    """
    return await message.answer(text)
