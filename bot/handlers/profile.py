"""
Обработчики создания и редактирования анкеты (FSM).
"""

import re
from datetime import date

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.keyboards.inline import (
    gender_keyboard,
    looking_for_keyboard,
    edit_profile_keyboard,
    profile_menu_keyboard,
    confirm_keyboard,
)
from bot.states import ProfileStates
from bot.api_client import APIClient

router = Router()

# Валидация возраста
AGE_PATTERN = re.compile(r"^(1[89]|[2-9]\d)$")


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

        await callback.message.answer(
            "🎉 Анкета создана!\n\n"
            "Теперь ты можешь:\n"
            "• Начать поиск анкет\n"
            "• Редактировать профиль\n"
            "• Добавить фотографии",
            reply_markup=profile_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Ошибка создания профиля: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка при создании профиля. Попробуй позже."
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

    # Формируем текст профиля
    interests = ", ".join(profile.get("interests", []))
    profile_text = (
        f"👤 <b>{profile.get('display_name', 'Аноним')}</b>\n"
        f"🎂 Возраст: {profile.get('age', 'не указан')}\n"
        f"⚧ Пол: {profile.get('gender', 'не указан')}\n"
        f"📍 Город: {profile.get('city', 'не указан')}\n"
        f"💕 Ищу: {profile.get('looking_for', 'не указано')}\n\n"
        f"📝 О себе: {profile.get('bio', 'не указано')}\n\n"
        f"🎯 Интересы: {interests if interests else 'не указаны'}"
    )

    await message.answer(
        profile_text,
        reply_markup=profile_menu_keyboard(),
    )


@router.callback_query(F.data == "edit_profile")
async def cb_edit_profile(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования профиля."""
    await callback.message.edit_text(
        "✏️ Что хочешь изменить?",
        reply_markup=edit_profile_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "edit_name")
async def cb_edit_name(callback: CallbackQuery, state: FSMContext):
    """Редактирование имени."""
    await callback.message.edit_text("👤 Введи новое имя:")
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

    await message.answer("✅ Имя обновлено!", reply_markup=profile_menu_keyboard())
    await state.clear()


@router.callback_query(F.data == "edit_bio")
async def cb_edit_bio(callback: CallbackQuery, state: FSMContext):
    """Редактирование описания."""
    await callback.message.edit_text("📝 Введи новое описание о себе:")
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

    await message.answer("✅ Описание обновлено!", reply_markup=profile_menu_keyboard())
    await state.clear()


@router.callback_query(F.data == "edit_city")
async def cb_edit_city(callback: CallbackQuery, state: FSMContext):
    """Редактирование города."""
    await callback.message.edit_text("📍 Введи новый город:")
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

    await message.answer("✅ Город обновлен!", reply_markup=profile_menu_keyboard())
    await state.clear()


@router.callback_query(F.data == "edit_interests")
async def cb_edit_interests(callback: CallbackQuery, state: FSMContext):
    """Редактирование интересов."""
    await callback.message.edit_text(
        "🎯 Введи новые интересы через запятую:\n"
        "Например: музыка, кино, спорт, путешествия"
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

    await message.answer("✅ Интересы обновлены!", reply_markup=profile_menu_keyboard())
    await state.clear()


@router.callback_query(F.data == "profile_done")
async def cb_profile_done(callback: CallbackQuery, state: FSMContext):
    """Завершение редактирования."""
    await callback.message.edit_text(
        "✅ Профиль обновлён!",
        reply_markup=profile_menu_keyboard(),
    )
    await state.clear()
    await callback.answer()
