"""
Обработчики для загрузки и управления фотографиями профиля.

Функционал:
- Загрузка фото через FSM (photo/document)
- Просмотр списка фото
- Удаление фото (с подтверждением)
- Назначение основного фото

UX-правило: callback-навигация по фото-flow обновляет уже показанный
экран через helper'ы из ``utils.message_editor`` и не плодит цепочки
новых сообщений.
"""

import os
import tempfile

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from keyboards.inline import (
    photos_list_keyboard,
    photo_action_keyboard,
    confirm_delete_photo_keyboard,
    profile_menu_keyboard,
)
from states import ProfileStates
from api_client import APIClient
from utils.message_editor import answer_temp, edit_or_answer, replace_with_photo, safe_delete

router = Router()

# Максимальный размер фото для загрузки — 10 МБ
MAX_PHOTO_SIZE = 10 * 1024 * 1024


# ============================================
# Рендеринг экрана фото
# ============================================


def _photos_screen_text(photos: list) -> str:
    """Собрать единый текст экрана со списком фото."""
    if not photos:
        return (
            "📸 У тебя пока нет фото.\n\n"
            "Нажми «📸 Добавить фото» чтобы загрузить первую фотографию."
        )

    lines = [f"📸 <b>Твои фото ({len(photos)} шт.)</b>", ""]
    for i, photo in enumerate(photos, 1):
        primary_marker = " ⭐ ОСНОВНОЕ" if photo.get("is_primary") else ""
        lines.append(f"<b>Фото {i}</b>{primary_marker}")
    lines.append("")
    lines.append("Нажми на фото в списке ниже, чтобы открыть его.")
    return "\n".join(lines)


async def _show_photos_screen(message: Message, api_client: APIClient, telegram_id: int) -> None:
    """Показать (через редактирование) актуальный экран со списком фото."""
    try:
        photos = await api_client.get_photos(telegram_id)
    except Exception as e:
        logger.error(f"[Photos] Ошибка получения списка фото: {e}")
        await edit_or_answer(
            message,
            "❌ Не удалось загрузить список фото. Попробуй позже.",
            reply_markup=profile_menu_keyboard(),
        )
        return

    if not photos:
        await edit_or_answer(
            message,
            _photos_screen_text(photos),
            reply_markup=profile_menu_keyboard(),
        )
        return

    await edit_or_answer(
        message,
        _photos_screen_text(photos),
        reply_markup=photos_list_keyboard(photos),
    )


# ============================================
# Загрузка фото
# ============================================


@router.callback_query(F.data == "add_photo")
async def cb_add_photo(callback: CallbackQuery, state: FSMContext):
    """Начало загрузки фото."""
    await edit_or_answer(
        callback.message,
        "📸 Отправь мне фотографию.\n\n"
        "💡 Ты можешь отправить фото как:\n"
        "• Обычное фото (сжатие Telegram)\n"
        "• Файл (без сжатия, лучшее качество)\n\n"
        "Максимум 6 фото на профиль, до 10 МБ каждая.",
    )
    await state.set_state(ProfileStates.waiting_for_photo)
    await callback.answer()


@router.message(ProfileStates.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext, api_client: APIClient):
    """Обработка загруженного фото."""
    # Берём фото в полном размере (последний элемент)
    photo_file = message.photo[-1]

    # Проверка размера
    if photo_file.file_size and photo_file.file_size > MAX_PHOTO_SIZE:
        await message.answer(
            f"❌ Фото слишком большое: {photo_file.file_size / 1024 / 1024:.1f} МБ (макс 10 МБ).\n"
            "Отправь другое фото."
        )
        return

    status_msg = await answer_temp(message, "⏳ Загружаю фото...")

    try:
        # Скачиваем файл во временный файл
        file = await message.bot.get_file(photo_file.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            await message.bot.download_file(file.file_path, tmp.name)
            tmp_path = tmp.name

        # Загружаем на backend
        await api_client.upload_photo(message.from_user.id, tmp_path)

        # Удаляем временный файл
        os.unlink(tmp_path)

        # Чистим в чате само пользовательское фото-сообщение
        await safe_delete(message)
        # Заменяем статус на актуальный экран фото
        await _show_photos_screen(status_msg, api_client, message.from_user.id)

    except Exception as e:
        logger.error(f"[Photos] Ошибка загрузки фото: {e}")
        await edit_or_answer(
            status_msg,
            "❌ Произошла ошибка при загрузке фото. Попробуй позже.",
            reply_markup=profile_menu_keyboard(),
        )

    await state.clear()


@router.message(ProfileStates.waiting_for_photo, F.document)
async def process_photo_as_document(message: Message, state: FSMContext, api_client: APIClient):
    """Обработка фото, отправленного как документ (без сжатия)."""
    doc = message.document

    # Проверка MIME типа
    if doc.mime_type and not doc.mime_type.startswith("image/"):
        await message.answer("❌ Это не изображение. Отправь фото.")
        return

    # Проверка размера
    if doc.file_size and doc.file_size > MAX_PHOTO_SIZE:
        await message.answer(
            f"❌ Файл слишком большой: {doc.file_size / 1024 / 1024:.1f} МБ (макс 10 МБ)."
        )
        return

    status_msg = await answer_temp(message, "⏳ Загружаю фото...")

    try:
        # Скачиваем файл
        file = await message.bot.get_file(doc.file_id)
        ext = doc.file_name.rsplit(".", 1)[-1] if doc.file_name and "." in doc.file_name else "jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            await message.bot.download_file(file.file_path, tmp.name)
            tmp_path = tmp.name

        # Загружаем на backend
        await api_client.upload_photo(message.from_user.id, tmp_path)

        # Удаляем временный файл
        os.unlink(tmp_path)

        # Чистим в чате само пользовательское фото-сообщение
        await safe_delete(message)
        await _show_photos_screen(status_msg, api_client, message.from_user.id)

    except Exception as e:
        logger.error(f"[Photos] Ошибка загрузки фото (document): {e}")
        await edit_or_answer(
            status_msg,
            "❌ Произошла ошибка при загрузке фото. Попробуй позже.",
            reply_markup=profile_menu_keyboard(),
        )

    await state.clear()


@router.message(ProfileStates.waiting_for_photo)
async def process_non_photo(message: Message):
    """Обработка не-фото сообщений в состоянии ожидания фото."""
    await message.answer(
        "❌ Пожалуйста, отправь фото (изображение или файл).\n"
        "Или нажми /cancel для отмены."
    )


# ============================================
# Управление фото
# ============================================


@router.callback_query(F.data == "list_photos")
async def cb_list_photos(callback: CallbackQuery, api_client: APIClient):
    """Показать список фото — единым редактируемым экраном."""
    await _show_photos_screen(callback.message, api_client, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data.startswith("photo_view:"))
async def cb_view_photo(callback: CallbackQuery, api_client: APIClient):
    """Просмотр конкретного фото — заменяет экран на само изображение."""
    photo_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    try:
        photos = await api_client.get_photos(telegram_id)
        photo = next((p for p in photos if p["id"] == photo_id), None)

        if not photo:
            await callback.answer("❌ Фото не найдено", show_alert=True)
            await _show_photos_screen(callback.message, api_client, telegram_id)
            return

        primary_marker = " ⭐ ОСНОВНОЕ" if photo.get("is_primary") else ""
        caption = (
            f"📸 <b>Фото</b>{primary_marker}\n\n"
            f"ID: {photo['id'][:8]}\n"
            f"Размер: {photo.get('file_size_bytes', 0) / 1024:.0f} КБ\n"
            f"Формат: {photo.get('mime_type', 'N/A')}"
        )
        kb = photo_action_keyboard(photo_id)

        # Грузим байты картинки и заменяем экран на photo-message
        photo_url = photo.get("url")
        photo_bytes = None
        if photo_url:
            photo_bytes = await api_client.fetch_photo_bytes(photo_url)

        if photo_bytes:
            await replace_with_photo(
                callback.message,
                photo_bytes=photo_bytes,
                caption=caption,
                reply_markup=kb,
                filename=f"photo_{photo_id[:8]}.jpg",
            )
        else:
            # Фолбэк: текст с предупреждением, но та же клавиатура и тот же экран
            await edit_or_answer(
                callback.message,
                caption + "\n\n⚠️ Превью недоступно.",
                reply_markup=kb,
            )

    except Exception as e:
        logger.error(f"[Photos] Ошибка просмотра фото: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
        return

    await callback.answer()


@router.callback_query(F.data.startswith("photo_primary:"))
async def cb_set_primary_photo(callback: CallbackQuery, api_client: APIClient):
    """Назначить фото основным — после операции возвращаем обновлённый список."""
    photo_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    try:
        await api_client.set_primary_photo(telegram_id, photo_id)
        await callback.answer("⭐ Это фото теперь основное!")
        await _show_photos_screen(callback.message, api_client, telegram_id)

    except Exception as e:
        logger.error(f"[Photos] Ошибка назначения основного фото: {e}")
        await callback.answer("❌ Не удалось обновить основное фото", show_alert=True)
        return


@router.callback_query(F.data.startswith("photo_delete:"))
async def cb_ask_delete_photo(callback: CallbackQuery):
    """Запрос подтверждения удаления фото."""
    photo_id = callback.data.split(":")[1]

    await edit_or_answer(
        callback.message,
        "⚠️ <b>Удалить это фото?</b>\n\nЭто действие нельзя отменить.",
        reply_markup=confirm_delete_photo_keyboard(photo_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("photo_delete_confirm:"))
async def cb_confirm_delete_photo(callback: CallbackQuery, api_client: APIClient):
    """Подтверждение удаления фото — после удаления показываем обновлённый список."""
    photo_id = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    try:
        await api_client.delete_photo(telegram_id, photo_id)
        await callback.answer("🗑 Фото удалено.")
        await _show_photos_screen(callback.message, api_client, telegram_id)

    except Exception as e:
        logger.error(f"[Photos] Ошибка удаления фото: {e}")
        await callback.answer("❌ Не удалось удалить фото", show_alert=True)


@router.callback_query(F.data == "back_to_photos")
async def cb_back_to_photos(callback: CallbackQuery, api_client: APIClient):
    """Возврат к списку фото — один редактируемый экран."""
    await _show_photos_screen(callback.message, api_client, callback.from_user.id)
    await callback.answer()
