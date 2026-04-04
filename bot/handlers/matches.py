"""
Обработчики для просмотра мэтчей.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.keyboards.inline import matches_keyboard
from bot.api_client import APIClient

router = Router()


@router.message(F.text == "/matches")
async def cmd_matches(message: Message, api_client: APIClient):
    """Показать список мэтчей."""
    telegram_id = message.from_user.id

    # Проверяем, есть ли профиль
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

        # Формируем список мэтчей
        matches_text = "💕 <b>Твои мэтчи:</b>\n\n"
        for match in matches:
            match_profile = match.get("profile", {})
            name = match_profile.get("display_name", "Аноним")
            city = match_profile.get("city", "")
            age = match_profile.get("age", "")

            line = f"👤 {name}"
            if age:
                line += f", {age}"
            if city:
                line += f", {city}"
            matches_text += line + "\n"

        matches_text += "\nНапиши /search чтобы продолжить поиск!"

        await message.answer(
            matches_text,
            reply_markup=matches_keyboard(),
        )

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
            matches_text = "💕 <b>Твои мэтчи:</b>\n\n"
            for match in matches:
                match_profile = match.get("profile", {})
                name = match_profile.get("display_name", "Аноним")
                city = match_profile.get("city", "")
                age = match_profile.get("age", "")

                line = f"👤 {name}"
                if age:
                    line += f", {age}"
                if city:
                    line += f", {city}"
                matches_text += line + "\n"

            await callback.message.edit_text(matches_text)

    except Exception as e:
        logger.error(f"Ошибка получения мэтчей: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

    await callback.answer()
