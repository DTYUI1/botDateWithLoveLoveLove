"""
Inline-клавиатуры для ConnectMe бота.
"""

from typing import Optional

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
            [InlineKeyboardButton(text="📸 Добавить фото", callback_data="add_photo"),
             InlineKeyboardButton(text="🖼 Мои фото", callback_data="list_photos")],
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
        ]
    )
    return keyboard


def match_chat_keyboard(username: Optional[str]) -> InlineKeyboardMarkup:
    """Клавиатура после состоявшегося мэтча.

    Если у партнёра есть @username — даём URL-кнопку, открывающую личку.
    Иначе — информационная кнопка-заглушка.
    """
    if username:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"💬 Написать @{username}",
                    url=f"https://t.me/{username}",
                )],
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="ℹ️ У партнёра не указан @username",
                callback_data="noop",
            )],
        ]
    )


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


def photos_list_keyboard(photos: list) -> InlineKeyboardMarkup:
    """Клавиатура списка фотографий.

    Args:
        photos: Список фото с полями id, is_primary, s3_key
    """
    keyboard = []
    for photo in photos:
        photo_id = photo["id"]
        is_primary = photo.get("is_primary", False)
        primary_label = " ⭐" if is_primary else ""

        keyboard.append([
            InlineKeyboardButton(
                text=f"📸 Фото {photo_id[:8]}{primary_label}",
                callback_data=f"photo_view:{photo_id}"
            )
        ])
        if not is_primary:
            keyboard.append([
                InlineKeyboardButton(
                    text="⭐ Сделать основным",
                    callback_data=f"photo_primary:{photo_id}"
                )
            ])
        keyboard.append([
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"photo_delete:{photo_id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад к профилю", callback_data="back_to_profile")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def photo_action_keyboard(photo_id: str) -> InlineKeyboardMarkup:
    """Клавиатура действий с конкретным фото."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐ Сделать основным",
                    callback_data=f"photo_primary:{photo_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"photo_delete:{photo_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад к списку",
                    callback_data="back_to_photos"
                ),
            ],
        ]
    )
    return keyboard


def confirm_delete_photo_keyboard(photo_id: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления фото."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Да, удалить",
                    callback_data=f"photo_delete_confirm:{photo_id}"
                ),
                InlineKeyboardButton(
                    text="⬅️ Отмена",
                    callback_data=f"photo_view:{photo_id}"
                ),
            ],
        ]
    )
    return keyboard


def back_to_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура возврата к профилю."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к профилю", callback_data="back_to_profile")],
        ]
    )
    return keyboard
