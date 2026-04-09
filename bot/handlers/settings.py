"""
Обработчики для управления настройками поиска.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from keyboards.inline import (
    looking_for_keyboard,
    confirm_keyboard,
)
from states import SearchStates
from api_client import APIClient

router = Router()


@router.message(F.text == "/settings")
async def cmd_settings(message: Message, api_client: APIClient):
    """Показать текущие настройки."""
    telegram_id = message.from_user.id
    logger.info(f"[Bot Settings] /settings от user_id={telegram_id}")

    # Проверяем, есть ли профиль
    profile = await api_client.get_profile(telegram_id)
    if not profile:
        await message.answer(
            "📝 Сначала создай анкету! Нажми /start чтобы начать."
        )
        return

    try:
        # Получаем настройки
        settings_data = await api_client.get_settings(telegram_id)

        if not settings_data:
            await message.answer("❌ Не удалось загрузить настройки. Попробуй позже.")
            return

        looking_for_map = {
            "male": "Парней",
            "female": "Девушек",
            "both": "Всех",
        }

        settings_text = (
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

        await message.answer(settings_text)

    except Exception as e:
        logger.error(f"[Bot Settings] Ошибка получения настроек: {e}")
        await message.answer("❌ Не удалось загрузить настройки. Попробуй позже.")


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

        await message.answer(f"✅ Диапазон возраста установлен: {age_min}-{age_max} лет")
        await state.clear()

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

        await message.answer(f"✅ Максимальное расстояние: {distance} км")
        await state.clear()

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
    """Обработка выбора ориентации в настройках."""
    looking_for = callback.data.replace("looking_", "")
    telegram_id = callback.from_user.id

    await api_client.update_settings(telegram_id, {
        "looking_for": looking_for,
    })

    looking_for_map = {
        "male": "Парней",
        "female": "Девушек",
        "both": "Всех",
    }

    await callback.message.edit_text(
        f"✅ Теперь ты ищешь: {looking_for_map.get(looking_for, looking_for)}"
    )
    await state.clear()
    await callback.answer()
