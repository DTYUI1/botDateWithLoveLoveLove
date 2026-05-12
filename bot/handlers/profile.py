"""
Обработчики создания и редактирования анкеты (FSM).
"""

import re

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from keyboards.inline import (
    gender_keyboard,
    looking_for_keyboard,
    edit_profile_keyboard,
    profile_menu_keyboard,
)
from states import ProfileStates
from api_client import APIClient
from utils.formatters import format_own_profile, GENDER_RU, LOOKING_FOR_RU
from utils.message_editor import edit_or_answer, safe_delete

router = Router()

# Валидация возраста
AGE_PATTERN = re.compile(r"^(1[89]|[2-9]\d)$")


def render_profile_text(profile: dict) -> str:
    """Собирает текст профиля для message/callback-сценариев."""
    return format_own_profile(profile)


async def _send_profile_screen(
    message: Message,
    api_client: APIClient,
    telegram_id: int,
) -> None:
    """Отправить новое сообщение с актуальным профилем (после FSM-text шагов)."""
    try:
        profile = await api_client.get_profile(telegram_id)
    except Exception as e:
        logger.error(f"[Profile] Ошибка получения профиля: {e}")
        await message.answer("❌ Не удалось открыть профиль. Попробуй позже.")
        return

    if not profile:
        await message.answer(
            "📝 У тебя ещё нет анкеты. Давай создадим её!\n"
            "Нажми /start чтобы начать.",
        )
        return

    await message.answer(
        render_profile_text(profile),
        reply_markup=profile_menu_keyboard(),
    )


async def _edit_profile_screen(
    message: Message,
    api_client: APIClient,
    telegram_id: int,
) -> None:
    """Заменить текущий экран на актуальный профиль (для callback-ответов)."""
    try:
        profile = await api_client.get_profile(telegram_id)
    except Exception as e:
        logger.error(f"[Profile] Ошибка получения профиля: {e}")
        await edit_or_answer(message, "❌ Не удалось открыть профиль. Попробуй позже.")
        return

    if not profile:
        await edit_or_answer(
            message,
            "📝 У тебя ещё нет анкеты. Давай создадим её!\n"
            "Нажми /start чтобы начать.",
        )
        return

    await edit_or_answer(
        message,
        render_profile_text(profile),
        reply_markup=profile_menu_keyboard(),
    )


# ============================================
# Создание профиля — пошаговый FSM
# ============================================


@router.message(ProfileStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Обработка имени пользователя."""
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("❌ Имя должно быть от 2 до 50 символов. Попробуй ещё раз:")
        return

    await state.update_data(name=name)
    await message.answer(
        "🎂 Сколько тебе лет? (введи число от 18 до 99):"
    )
    await state.set_state(ProfileStates.waiting_for_age)
    await safe_delete(message)


@router.message(ProfileStates.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    """Обработка возраста."""
    age_text = message.text.strip()

    if not AGE_PATTERN.match(age_text):
        await message.answer("❌ Возраст должен быть от 18 до 99 лет. Попробуй ещё раз:")
        return

    await state.update_data(age=int(age_text))
    await message.answer(
        "⚧ Укажи свой пол:",
        reply_markup=gender_keyboard(),
    )
    await state.set_state(ProfileStates.waiting_for_gender)
    await safe_delete(message)


@router.callback_query(F.data.startswith("gender_"), ProfileStates.waiting_for_gender)
async def process_gender(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора пола."""
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    await callback.message.edit_text(
        "📝 Расскажи о себе в нескольких словах. Чем ты увлекаешься? Что тебя вдохновляет?"
    )
    await state.set_state(ProfileStates.waiting_for_bio)
    await callback.answer()


@router.message(ProfileStates.waiting_for_bio)
async def process_bio(message: Message, state: FSMContext):
    """Обработка описания профиля."""
    bio = message.text.strip()
    if len(bio) < 10:
        await message.answer("❌ Расскажи немного больше о себе (минимум 10 символов):")
        return
    if len(bio) > 500:
        await message.answer("❌ Описание слишком длинное. Сократи до 500 символов:")
        return

    await state.update_data(bio=bio)
    await message.answer(
        "🎯 Напиши свои интересы через запятую.\n"
        "Например: музыка, кино, спорт, путешествия, программирование:"
    )
    await state.set_state(ProfileStates.waiting_for_interests)
    await safe_delete(message)


@router.message(ProfileStates.waiting_for_interests)
async def process_interests(message: Message, state: FSMContext):
    """Обработка интересов."""
    interests_text = message.text.strip()
    interests = [i.strip().lower() for i in interests_text.split(",") if i.strip()]

    if len(interests) < 1:
        await message.answer("❌ Укажи хотя бы один интерес:")
        return

    await state.update_data(interests=interests)
    await message.answer(
        "📍 В каком городе ты находишься?"
    )
    await state.set_state(ProfileStates.waiting_for_city)
    await safe_delete(message)


@router.message(ProfileStates.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    """Обработка города."""
    city = message.text.strip()
    if len(city) < 2:
        await message.answer("❌ Укажи корректное название города:")
        return

    await state.update_data(city=city)
    await message.answer(
        "💕 Кого ты ищешь?",
        reply_markup=looking_for_keyboard(),
    )
    await state.set_state(ProfileStates.waiting_for_looking_for)
    await safe_delete(message)


@router.callback_query(F.data.startswith("looking_"), ProfileStates.waiting_for_looking_for)
async def process_looking_for(callback: CallbackQuery, state: FSMContext, api_client: APIClient):
    """Обработка выбора ориентации поиска и сохранение профиля."""
    looking_for = callback.data.replace("looking_", "")
    await state.update_data(looking_for=looking_for)

    # Получаем данные из состояния
    data = await state.get_data()
    telegram_id = callback.from_user.id

    # Формируем данные профиля
    profile_data = {
        "display_name": data.get("name"),
        "age": data.get("age"),
        "gender": data.get("gender"),
        "bio": data.get("bio"),
        "interests": data.get("interests", []),
        "city": data.get("city"),
        "looking_for": data.get("looking_for"),
    }

    await callback.message.edit_text("⏳ Сохраняю твой профиль...")

    try:
        # Создаём профиль через API
        await api_client.create_profile(telegram_id, profile_data)

        await edit_or_answer(
            callback.message,
            "🎉 Анкета создана!\n\n"
            "Теперь ты можешь:\n"
            "• Начать поиск анкет\n"
            "• Редактировать профиль\n"
            "• Добавить фотографии",
            reply_markup=profile_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Ошибка создания профиля: {e}")
        await edit_or_answer(
            callback.message,
            "❌ Произошла ошибка при создании профиля. Попробуй позже.",
        )

    await state.clear()
    await callback.answer()


# ============================================
# Просмотр и редактирование профиля
# ============================================


@router.message(F.text == "/profile")
async def cmd_profile(message: Message, state: FSMContext, api_client: APIClient):
    """Показать свой профиль."""
    telegram_id = message.from_user.id
    profile = await api_client.get_profile(telegram_id)

    if not profile:
        await message.answer(
            "📝 У тебя ещё нет анкеты. Давай создадим её!\n"
            "Нажми /start чтобы начать.",
        )
        return

    await message.answer(
        render_profile_text(profile),
        reply_markup=profile_menu_keyboard(),
    )


@router.callback_query(F.data == "back_to_profile")
async def cb_back_to_profile(callback: CallbackQuery, api_client: APIClient):
    """Вернуть пользователя к актуальному экрану профиля."""
    await callback.answer()
    await _edit_profile_screen(callback.message, api_client, callback.from_user.id)


@router.callback_query(F.data == "edit_profile")
async def cb_edit_profile(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования профиля."""
    await edit_or_answer(
        callback.message,
        "✏️ Что хочешь изменить?",
        reply_markup=edit_profile_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "edit_name")
async def cb_edit_name(callback: CallbackQuery, state: FSMContext):
    """Редактирование имени."""
    await edit_or_answer(callback.message, "👤 Введи новое имя:")
    await state.set_state(ProfileStates.editing_name)
    await callback.answer()


@router.message(ProfileStates.editing_name)
async def process_edit_name(message: Message, state: FSMContext, api_client: APIClient):
    """Сохранение нового имени."""
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("❌ Имя должно быть от 2 до 50 символов:")
        return

    telegram_id = message.from_user.id
    await api_client.update_profile(telegram_id, {"display_name": name})

    await state.clear()
    await safe_delete(message)
    await _send_profile_screen(message, api_client, telegram_id)


@router.callback_query(F.data == "edit_age")
async def cb_edit_age(callback: CallbackQuery, state: FSMContext):
    """Редактирование возраста."""
    await edit_or_answer(callback.message, "🎂 Введи новый возраст (от 18 до 99):")
    await state.set_state(ProfileStates.editing_age)
    await callback.answer()


@router.message(ProfileStates.editing_age)
async def process_edit_age(message: Message, state: FSMContext, api_client: APIClient):
    """Сохранение нового возраста."""
    age_text = message.text.strip()

    if not AGE_PATTERN.match(age_text):
        await message.answer("❌ Возраст должен быть от 18 до 99 лет. Попробуй ещё раз:")
        return

    telegram_id = message.from_user.id
    await api_client.update_profile(telegram_id, {"age": int(age_text)})

    await state.clear()
    await safe_delete(message)
    await _send_profile_screen(message, api_client, telegram_id)


@router.callback_query(F.data == "edit_gender")
async def cb_edit_gender(callback: CallbackQuery, state: FSMContext):
    """Редактирование пола."""
    await edit_or_answer(
        callback.message,
        "⚧ Укажи свой пол:",
        reply_markup=gender_keyboard(),
    )
    await state.set_state(ProfileStates.editing_gender)
    await callback.answer()


@router.callback_query(F.data.startswith("gender_"), ProfileStates.editing_gender)
async def process_edit_gender(callback: CallbackQuery, state: FSMContext, api_client: APIClient):
    """Сохранение нового пола."""
    gender = callback.data.replace("gender_", "")
    telegram_id = callback.from_user.id
    await api_client.update_profile(telegram_id, {"gender": gender})

    await state.clear()
    await callback.answer(f"Пол: {GENDER_RU.get(gender, gender)}")
    await _edit_profile_screen(callback.message, api_client, telegram_id)


@router.callback_query(F.data == "edit_looking_for")
async def cb_edit_looking_for(callback: CallbackQuery, state: FSMContext):
    """Редактирование предпочтений поиска."""
    await edit_or_answer(
        callback.message,
        "💕 Кого ты ищешь?",
        reply_markup=looking_for_keyboard(),
    )
    await state.set_state(ProfileStates.editing_looking_for)
    await callback.answer()


@router.callback_query(F.data.startswith("looking_"), ProfileStates.editing_looking_for)
async def process_edit_looking_for(callback: CallbackQuery, state: FSMContext, api_client: APIClient):
    """Сохранение новых предпочтений поиска."""
    looking_for = callback.data.replace("looking_", "")
    telegram_id = callback.from_user.id
    await api_client.update_profile(telegram_id, {"looking_for": looking_for})

    await state.clear()
    await callback.answer(f"Ищешь: {LOOKING_FOR_RU.get(looking_for, looking_for)}")
    await _edit_profile_screen(callback.message, api_client, telegram_id)


@router.callback_query(F.data == "edit_bio")
async def cb_edit_bio(callback: CallbackQuery, state: FSMContext):
    """Редактирование описания."""
    await edit_or_answer(callback.message, "📝 Введи новое описание о себе:")
    await state.set_state(ProfileStates.editing_bio)
    await callback.answer()


@router.message(ProfileStates.editing_bio)
async def process_edit_bio(message: Message, state: FSMContext, api_client: APIClient):
    """Сохранение нового описания."""
    bio = message.text.strip()
    if len(bio) < 10:
        await message.answer("❌ Расскажи немного больше (минимум 10 символов):")
        return

    telegram_id = message.from_user.id
    await api_client.update_profile(telegram_id, {"bio": bio})

    await state.clear()
    await safe_delete(message)
    await _send_profile_screen(message, api_client, telegram_id)


@router.callback_query(F.data == "edit_city")
async def cb_edit_city(callback: CallbackQuery, state: FSMContext):
    """Редактирование города."""
    await edit_or_answer(callback.message, "📍 Введи новый город:")
    await state.set_state(ProfileStates.editing_city)
    await callback.answer()


@router.message(ProfileStates.editing_city)
async def process_edit_city(message: Message, state: FSMContext, api_client: APIClient):
    """Сохранение нового города."""
    city = message.text.strip()
    if len(city) < 2:
        await message.answer("❌ Укажи корректное название города:")
        return

    telegram_id = message.from_user.id
    await api_client.update_profile(telegram_id, {"city": city})

    await state.clear()
    await safe_delete(message)
    await _send_profile_screen(message, api_client, telegram_id)


@router.callback_query(F.data == "edit_interests")
async def cb_edit_interests(callback: CallbackQuery, state: FSMContext):
    """Редактирование интересов."""
    await edit_or_answer(
        callback.message,
        "🎯 Введи новые интересы через запятую:\n"
        "Например: музыка, кино, спорт, путешествия",
    )
    await state.set_state(ProfileStates.editing_interests)
    await callback.answer()


@router.message(ProfileStates.editing_interests)
async def process_edit_interests(message: Message, state: FSMContext, api_client: APIClient):
    """Сохранение новых интересов."""
    interests_text = message.text.strip()
    interests = [i.strip().lower() for i in interests_text.split(",") if i.strip()]

    if len(interests) < 1:
        await message.answer("❌ Укажи хотя бы один интерес:")
        return

    telegram_id = message.from_user.id
    await api_client.update_profile(telegram_id, {"interests": interests})

    await state.clear()
    await safe_delete(message)
    await _send_profile_screen(message, api_client, telegram_id)


@router.callback_query(F.data == "profile_done")
async def cb_profile_done(callback: CallbackQuery, state: FSMContext, api_client: APIClient):
    """Завершение редактирования — возвращаемся к экрану профиля."""
    await state.clear()
    await callback.answer("✅ Профиль обновлён")
    await _edit_profile_screen(callback.message, api_client, callback.from_user.id)
