"""
Обработчики для просмотра мэтчей.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger

from api_client import APIClient
from utils.formatters import format_match_line

router = Router()


def _build_matches_view(matches: list) -> tuple[str, InlineKeyboardMarkup]:
    """Собирает текст списка мэтчей и URL-кнопки 'Написать @username' для каждого."""
    lines = ["💕 <b>Твои мэтчи:</b>", ""]
    keyboard_rows: list[list[InlineKeyboardButton]] = []

    for match in matches:
        match_profile = match.get("profile", {}) or {}
        username = match_profile.get("username")
        name = match_profile.get("display_name") or "Аноним"

        lines.append(format_match_line(match_profile))

        if username:
            keyboard_rows.append([InlineKeyboardButton(
                text=f"💬 Написать {name} (@{username})",
                url=f"https://t.me/{username}",
            )])
        else:
            keyboard_rows.append([InlineKeyboardButton(
                text=f"ℹ️ {name} — без @username",
                callback_data="noop",
            )])

    lines.append("")
    lines.append("Напиши /search чтобы продолжить поиск!")
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


@router.message(F.text == "/matches")
async def cmd_matches(message: Message, api_client: APIClient):
    """Показать список мэтчей."""
    telegram_id = message.from_user.id

    profile = await api_client.get_profile(telegram_id)
    if not profile:
        await message.answer(
            "📝 Сначала создай анкету! Нажми /start чтобы начать."
        )
        return

    try:
        matches = await api_client.get_matches(telegram_id)

        if not matches:
            await message.answer(
                "💔 У тебя пока нет мэтчей.\n\n"
                "Продолжай свайпать анкеты — и мэтч обязательно случится! 💕\n\n"
                "Используй /search чтобы начать поиск."
            )
            return

        text, kb = _build_matches_view(matches)
        await message.answer(text, reply_markup=kb)

    except Exception as e:
        logger.error(f"Ошибка получения мэтчей: {e}")
        await message.answer("❌ Произошла ошибка. Попробуй позже.")


@router.callback_query(F.data == "list_matches")
async def cb_list_matches(callback: CallbackQuery, api_client: APIClient):
    """Показать мэтчи из inline-клавиатуры."""
    telegram_id = callback.from_user.id

    try:
        matches = await api_client.get_matches(telegram_id)

        if not matches:
            await callback.message.edit_text(
                "💔 У тебя пока нет мэтчей.\n"
                "Продолжай свайпать анкеты!"
            )
        else:
            text, kb = _build_matches_view(matches)
            await callback.message.edit_text(text, reply_markup=kb)

    except Exception as e:
        logger.error(f"Ошибка получения мэтчей: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()
