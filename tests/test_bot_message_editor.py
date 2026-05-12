"""Тесты для `bot/utils/message_editor.py`.

Проверяем:
- успешный `edit_text` для текстового сообщения;
- fallback на `answer`, если редактирование невозможно;
- безопасное поведение `safe_delete` при ошибке.

Все aiogram-объекты мокируем без обращения к Telegram API.
"""

import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock

# Делаем `bot/` импортируемым.
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "bot")
)


@pytest.fixture
def message_module():
    """Импортирует helper. Локально, чтобы не падать на этапе сбора, если бот не в PYTHONPATH."""
    from utils import message_editor  # noqa: WPS433
    return message_editor


def _make_message(*, has_photo: bool = False) -> MagicMock:
    """Лёгкий мок aiogram.types.Message: только поля, нужные helper'у."""
    message = MagicMock()
    # has_media() читает эти атрибуты
    message.photo = [MagicMock()] if has_photo else None
    message.video = None
    message.animation = None
    message.document = None
    message.edit_text = AsyncMock(return_value="edited")
    message.edit_caption = AsyncMock(return_value="edited-caption")
    message.edit_reply_markup = AsyncMock(return_value="markup-edited")
    message.answer = AsyncMock(return_value="answered")
    message.delete = AsyncMock(return_value=None)
    return message


@pytest.mark.asyncio
async def test_edit_or_answer_uses_edit_text_for_text_message(message_module):
    """Для текстового сообщения вызываем edit_text и не дёргаем answer."""
    message = _make_message(has_photo=False)

    result = await message_module.edit_or_answer(message, "hello")

    assert result == "edited"
    message.edit_text.assert_awaited_once()
    message.answer.assert_not_called()
    message.delete.assert_not_called()


@pytest.mark.asyncio
async def test_edit_or_answer_falls_back_to_answer_when_edit_fails(message_module):
    """Если edit_text/edit_caption бросает не-BadRequest исключение — fallback на answer."""
    message = _make_message(has_photo=False)
    message.edit_text.side_effect = RuntimeError("boom")

    result = await message_module.edit_or_answer(message, "hello")

    assert result == "answered"
    message.delete.assert_awaited_once()
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_edit_or_answer_replaces_media_message_with_text(message_module):
    """Photo-сообщение должно быть удалено и заменено новым текстом —
    edit_caption НЕ должен использоваться, иначе старая картинка "залипает".
    """
    message = _make_message(has_photo=True)

    result = await message_module.edit_or_answer(message, "новый текст")

    assert result == "answered"
    message.delete.assert_awaited_once()
    message.answer.assert_awaited_once()
    message.edit_caption.assert_not_called()
    message.edit_text.assert_not_called()


@pytest.mark.asyncio
async def test_safe_delete_swallows_errors(message_module):
    """safe_delete не должен пробрасывать исключения наверх."""
    message = _make_message()
    message.delete.side_effect = RuntimeError("cannot delete")

    # Не должно бросать.
    await message_module.safe_delete(message)
    await message_module.safe_delete(None)

    message.delete.assert_awaited_once()
