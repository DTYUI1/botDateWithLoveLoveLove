"""
Обработчики для управления настройками поиска.

UX-правило: callback `settings` редактирует текущий экран,
а успешные изменения возвращают пользователя на обновлённый экран
настроек, а не плодят отдельные success-сообщения.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from keyboards.inline import (
    looking_for_keyboard,
)
from states import SearchStates
from api_client import APIClient
from utils.message_editor import edit_or_answer, safe_delete

router = Router()


def render_settings_text(settings_data: dict) -> str:
    """Собирает текст настроек поиска для message/callback-сценариев."""
    looking_for_map = {
        "male": "Парней",
        "female": "Девушек",
        "both": "Всех",
    }

    return (
        "⚙️ <b>Твои настройки поиска:</b>\n\n"
        f"🎂 Возраст: {settings_data.get('age_range_min', 18)}-{settings_data.get('age_range_max', 100)} лет\n"
        f"📏 Расстояние: до {settings_data.get('distance_max_km', 100)} км\n"
        f"💕 Ищу: {looking_for_map.get(settings_data.get('looking_for', 'both'), 'Всех')}\n"
        f"📍 Город: {settings_data.get('city', 'не указан')}\n\n"
        "Что хочешь изменить?\n\n"
        "Используй команды:\n"
        "/settings_age — изменить диапазон возраста\n"
        "/settings_distance — изменить расстояние\n"
        "/settings_looking — изменить кого ищешь\n"
    )


async def _send_settings_screen(message: Message, api_client: APIClient, telegram_id: int) -> None:
    """Отправить новое сообщение со снимком настроек (для команд)."""
    try:
        settings_data = await api_client.get_settings(telegram_id)
        if not settings_data:
            await message.answer("❌ Не удалось загрузить настройки. Попробуй позже.")
            return
        await message.answer(render_settings_text(settings_data))
    except Exception as e:
        logger.error(f"[Bot Settings] Ошибка получения настроек: {e}")
        await message.answer("❌ Не удалось загрузить настройки. Попробуй позже.")


async def _edit_settings_screen(message: Message, api_client: APIClient, telegram_id: int) -> None:
    """Заменить текущий экран на обновлённые настройки."""
    try:
        settings_data = await api_client.get_settings(telegram_id)
        if not settings_data:
            await edit_or_answer(message, "❌ Не удалось загрузить настройки. Попробуй позже.")
            return
        await edit_or_answer(message, render_settings_text(settings_data))
    except Exception as e:
        logger.error(f"[Bot Settings] Ошибка получения настроек: {e}")
        await edit_or_answer(message, "❌ Не удалось загрузить настройки. Попробуй позже.")


@router.message(F.text == "/settings")
async def cmd_settings(message: Message, api_client: APIClient):
    """Показать текущие настройки (команда — новый экран)."""
    telegram_id = message.from_user.id
    logger.info(f"[Bot Settings] /settings от user_id={telegram_id}")

    profile = await api_client.get_profile(telegram_id)
    if not profile:
        await message.answer("📝 Сначала создай анкету! Нажми /start чтобы начать.")
        return

    await _send_settings_screen(message, api_client, telegram_id)


@router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery, api_client: APIClient):
    """Открыть настройки из inline-кнопки профиля — редактируем экран."""
    await callback.answer()

    telegram_id = callback.from_user.id
    logger.info(f"[Bot Settings] callback settings от user_id={telegram_id}")

    profile = await api_client.get_profile(telegram_id)
    if not profile:
        await edit_or_answer(
            callback.message,
            "📝 Сначала создай анкету! Нажми /start чтобы начать.",
        )
        return

    await _edit_settings_screen(callback.message, api_client, telegram_id)


@router.message(F.text == "/settings_age")
async def cmd_settings_age(message: Message, state: FSMContext):
    """Изменить диапазон возраста."""
    await message.answer(
        "🎂 Введи минимальный возраст (от 18):"
    )
    await state.set_state(SearchStates.editing_age_range_min)


@router.message(SearchStates.editing_age_range_min)
async def process_age_min(message: Message, state: FSMContext, api_client: APIClient):
    """Обработка минимального возраста."""
    try:
        age_min = int(message.text.strip())
        if age_min < 18 or age_min > 99:
            await message.answer("❌ Возраст должен быть от 18 до 99. Попробуй ещё раз:")
            return

        await state.update_data(age_range_min=age_min)
        await message.answer("🎂 Введи максимальный возраст:")
        await state.set_state(SearchStates.editing_age_range_max)
        await safe_delete(message)

    except ValueError:
        await message.answer("❌ Введи число. Попробуй ещё раз:")


@router.message(SearchStates.editing_age_range_max)
async def process_age_max(message: Message, state: FSMContext, api_client: APIClient):
    """Обработка максимального возраста."""
    try:
        age_max = int(message.text.strip())
        if age_max < 19 or age_max > 100:
            await message.answer("❌ Возраст должен быть от 19 до 100. Попробуй ещё раз:")
            return

        data = await state.get_data()
        age_min = data.get("age_range_min", 18)

        if age_max <= age_min:
            await message.answer(f"❌ Максимальный возраст должен быть больше {age_min}. Попробуй ещё раз:")
            return

        telegram_id = message.from_user.id
        await api_client.update_settings(telegram_id, {
            "age_range_min": age_min,
            "age_range_max": age_max,
        })

        await state.clear()
        await safe_delete(message)
        # Вместо отдельного success-сообщения — сразу обновлённый экран настроек
        await _send_settings_screen(message, api_client, telegram_id)

    except ValueError:
        await message.answer("❌ Введи число. Попробуй ещё раз:")


@router.message(F.text == "/settings_distance")
async def cmd_settings_distance(message: Message, state: FSMContext):
    """Изменить максимальное расстояние."""
    await message.answer(
        "📏 Введи максимальное расстояние в км (от 1 до 500):"
    )
    await state.set_state(SearchStates.editing_distance)


@router.message(SearchStates.editing_distance)
async def process_distance(message: Message, state: FSMContext, api_client: APIClient):
    """Обработка расстояния."""
    try:
        distance = int(message.text.strip())
        if distance < 1 or distance > 500:
            await message.answer("❌ Расстояние должно быть от 1 до 500 км. Попробуй ещё раз:")
            return

        telegram_id = message.from_user.id
        await api_client.update_settings(telegram_id, {
            "distance_max_km": distance,
        })

        await state.clear()
        await safe_delete(message)
        await _send_settings_screen(message, api_client, telegram_id)

    except ValueError:
        await message.answer("❌ Введи число. Попробуй ещё раз:")


@router.message(F.text == "/settings_looking")
async def cmd_settings_looking(message: Message, state: FSMContext):
    """Изменить ориентацию поиска."""
    await message.answer(
        "💕 Кого ты ищешь?",
        reply_markup=looking_for_keyboard(),
    )
    await state.set_state(SearchStates.editing_looking_for_settings)


@router.callback_query(
    F.data.startswith("looking_"),
    SearchStates.editing_looking_for_settings
)
async def process_looking_for_settings(
    callback: CallbackQuery,
    state: FSMContext,
    api_client: APIClient,
):
    """Обработка выбора ориентации в настройках — возвращаем обновлённый экран."""
    looking_for = callback.data.replace("looking_", "")
    telegram_id = callback.from_user.id

    await api_client.update_settings(telegram_id, {
        "looking_for": looking_for,
    })

    await state.clear()
    await callback.answer()
    await _edit_settings_screen(callback.message, api_client, telegram_id)
