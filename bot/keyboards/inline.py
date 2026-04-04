"""
Inline-клавиатуры для ConnectMe бота.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для команды /start."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Создать анкету", callback_data="create_profile")],
            [InlineKeyboardButton(text="ℹ️ О боте", callback_data="about")],
        ]
    )
    return keyboard


def profile_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура меню профиля."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Редактировать профиль", callback_data="edit_profile")],
            [InlineKeyboardButton(text="📸 Добавить фото", callback_data="add_photo")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
            [InlineKeyboardButton(text="🔍 Начать поиск", callback_data="start_search")],
        ]
    )
    return keyboard


def edit_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура редактирования профиля."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Имя", callback_data="edit_name")],
            [InlineKeyboardButton(text="🎂 Возраст", callback_data="edit_age")],
            [InlineKeyboardButton(text="⚧ Пол", callback_data="edit_gender")],
            [InlineKeyboardButton(text="📝 О себе", callback_data="edit_bio")],
            [InlineKeyboardButton(text="🎯 Интересы", callback_data="edit_interests")],
            [InlineKeyboardButton(text="📍 Город", callback_data="edit_city")],
            [InlineKeyboardButton(text="💕 Кого ищу", callback_data="edit_looking_for")],
            [InlineKeyboardButton(text="✅ Готово", callback_data="profile_done")],
        ]
    )
    return keyboard


def swipe_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для свайпов (лайк/пропуск)."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Пропустить", callback_data="swipe_pass"),
                InlineKeyboardButton(text="❤️ Лайк", callback_data="swipe_like"),
            ],
            [InlineKeyboardButton(text="💬 Написать", callback_data="open_chat")],
        ]
    )
    return keyboard


def matches_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для списка мэтчей."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Мои мэтчи", callback_data="list_matches")],
            [InlineKeyboardButton(text="🎁 Идеи для свиданий", callback_data="date_ideas")],
        ]
    )
    return keyboard


def gender_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора пола."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male"),
                InlineKeyboardButton(text="👩 Женский", callback_data="gender_female"),
            ],
            [InlineKeyboardButton(text="🌐 Другой", callback_data="gender_other")],
        ]
    )
    return keyboard


def looking_for_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора ориентации поиска."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Парня", callback_data="looking_male"),
                InlineKeyboardButton(text="👩 Девушку", callback_data="looking_female"),
            ],
            [InlineKeyboardButton(text="💕 Всех", callback_data="looking_both")],
        ]
    )
    return keyboard


def confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="confirm_yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no"),
            ],
        ]
    )
    return keyboard
