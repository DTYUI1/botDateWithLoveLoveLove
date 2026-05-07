"""
Обработчики для загрузки и управления фотографиями профиля.

Функционал:
- Загрузка фото через FSM (photo/document)
- Просмотр списка фото
- Удаление фото (с подтверждением)
- Назначение основного фото
"""

import os
import tempfile

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
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

router = Router()

# Максимальный размер фото для загрузки — 10 МБ
MAX_PHOTO_SIZE = 10 * 1024 * 1024


# ============================================
# Загрузка фото
# ============================================


@router.callback_query(F.data == "add_photo")
async def cb_add_photo(callback: CallbackQuery, state: FSMContext):
    """Начало загрузки фото."""
    await callback.message.edit_text(
        "📸 Отправь мне фотографию.\n\n"
        "💡 Ты можешь отправить фото как:\n"
        "• Обычное фото (сжатие Telegram)\n"
        "• Файл (без сжатия, лучшее качество)\n\n"
        "Максимум 6 фото на профиль, до 10 МБ каждая."
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

    await message.answer("⏳ Загружаю фото...")

    try:
        # Скачиваем файл во временный файл
        file = await message.bot.get_file(photo_file.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            await message.bot.download_file(file.file_path, tmp.name)
            tmp_path = tmp.name

        # Загружаем на backend
        result = await api_client.upload_photo(message.from_user.id, tmp_path)

        # Удаляем временный файл
        os.unlink(tmp_path)

        is_primary = result.get("is_primary", False)
        primary_note = "\n⭐ Это фото стало основным!" if is_primary else ""

        await message.answer(
            f"✅ Фото успешно загружено!{primary_note}\n\n"
            "Что хочешь сделать дальше?",
            reply_markup=profile_menu_keyboard(),
        )

    except Exception as e:
        logger.error(f"[Photos] Ошибка загрузки фото: {e}")
        await message.answer(
            "❌ Произошла ошибка при загрузке фото. Попробуй позже."
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

    await message.answer("⏳ Загружаю фото...")

    try:
        # Скачиваем файл
        file = await message.bot.get_file(doc.file_id)
        ext = doc.file_name.rsplit(".", 1)[-1] if doc.file_name and "." in doc.file_name else "jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            await message.bot.download_file(file.file_path, tmp.name)
            tmp_path = tmp.name

        # Загружаем на backend
        result = await api_client.upload_photo(message.from_user.id, tmp_path)

        # Удаляем временный файл
        os.unlink(tmp_path)

        is_primary = result.get("is_primary", False)
        primary_note = "\n⭐ Это фото стало основным!" if is_primary else ""

        await message.answer(
            f"✅ Фото успешно загружено!{primary_note}\n\n"
            "Что хочешь сделать дальше?",
            reply_markup=profile_menu_keyboard(),
        )

    except Exception as e:
        logger.error(f"[Photos] Ошибка загрузки фото (document): {e}")
        await message.answer(
            "❌ Произошла ошибка при загрузке фото. Попробуй позже."
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


async def _send_photos_gallery(message, photos: list, api_client: APIClient) -> None:
    """Отправить настоящие фото пользователю + общую клавиатуру управления."""
    photos_count = len(photos)
    await message.answer(f"📸 <b>Твои фото ({photos_count} шт.)</b>")

    for i, photo in enumerate(photos, 1):
        primary_marker = " ⭐ ОСНОВНОЕ" if photo.get("is_primary") else ""
        caption = f"<b>Фото {i}</b>{primary_marker}"
        url = photo.get("url")
        photo_bytes = None
        if url:
            photo_bytes = await api_client.fetch_photo_bytes(url)
        if photo_bytes:
            try:
                await message.answer_photo(
                    photo=BufferedInputFile(photo_bytes, filename=f"photo_{i}.jpg"),
                    caption=caption,
                )
                continue
            except Exception as e:
                logger.warning(f"[Photos] Не удалось отправить фото {photo.get('id')}: {e}")
        await message.answer(f"{caption}\n⚠️ Превью недоступно.")

    await message.answer(
        "Выбери действие:",
        reply_markup=photos_list_keyboard(photos),
    )


@router.callback_query(F.data == "list_photos")
async def cb_list_photos(callback: CallbackQuery, api_client: APIClient):
    """Показать список фото."""
    telegram_id = callback.from_user.id

    try:
        photos = await api_client.get_photos(telegram_id)

        if not photos:
            await callback.message.edit_text(
                "📸 У тебя пока нет фото.\n\n"
                "Нажми «📸 Добавить фото» чтобы загрузить первую фотографию."
            )
            await callback.answer()
            return

        await _send_photos_gallery(callback.message, photos, api_client)

    except Exception as e:
        logger.error(f"[Photos] Ошибка получения списка фото: {e}")
        await callback.answer("❌ Не удалось загрузить список фото", show_alert=True)

    await callback.answer()


@router.callback_query(F.data.startswith("photo_view:"))
async def cb_view_photo(callback: CallbackQuery, api_client: APIClient):
    """Просмотр конкретного фото."""
    photo_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    try:
        photos = await api_client.get_photos(telegram_id)
        photo = next((p for p in photos if p["id"] == photo_id), None)

        if not photo:
            await callback.answer("❌ Фото не найдено", show_alert=True)
            return

        primary_marker = " ⭐ ОСНОВНОЕ" if photo.get("is_primary") else ""
        text = (
            f"📸 <b>Фото</b>{primary_marker}\n\n"
            f"ID: {photo['id'][:8]}\n"
            f"Размер: {photo.get('file_size_bytes', 0) / 1024:.0f} КБ\n"
            f"Формат: {photo.get('mime_type', 'N/A')}\n"
            f"Загружено: {photo.get('created_at', 'N/A')}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=photo_action_keyboard(photo_id),
        )

    except Exception as e:
        logger.error(f"[Photos] Ошибка просмотра фото: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

    await callback.answer()


@router.callback_query(F.data.startswith("photo_primary:"))
async def cb_set_primary_photo(callback: CallbackQuery, api_client: APIClient):
    """Назначить фото основным."""
    photo_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    try:
        await api_client.set_primary_photo(telegram_id, photo_id)
        await callback.message.answer("⭐ Это фото теперь основное!")

        photos = await api_client.get_photos(telegram_id)
        if photos:
            await _send_photos_gallery(callback.message, photos, api_client)

    except Exception as e:
        logger.error(f"[Photos] Ошибка назначения основного фото: {e}")
        await callback.answer("❌ Не удалось обновить основное фото", show_alert=True)

    await callback.answer()


@router.callback_query(F.data.startswith("photo_delete:"))
async def cb_ask_delete_photo(callback: CallbackQuery):
    """Запрос подтверждения удаления фото."""
    photo_id = callback.data.split(":")[1]

    await callback.message.edit_text(
        "⚠️ <b>Удалить это фото?</b>\n\n"
        "Это действие нельзя отменить.",
        reply_markup=confirm_delete_photo_keyboard(photo_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("photo_delete_confirm:"))
async def cb_confirm_delete_photo(callback: CallbackQuery, api_client: APIClient):
    """Подтверждение удаления фото."""
    photo_id = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    try:
        await api_client.delete_photo(telegram_id, photo_id)
        await callback.message.edit_text("🗑 Фото удалено.")

        photos = await api_client.get_photos(telegram_id)
        if photos:
            await _send_photos_gallery(callback.message, photos, api_client)
        else:
            await callback.message.answer(
                "📸 У тебя пока нет фото.\n\n"
                "Нажми «📸 Добавить фото» чтобы загрузить первую фотографию.",
                reply_markup=profile_menu_keyboard(),
            )

    except Exception as e:
        logger.error(f"[Photos] Ошибка удаления фото: {e}")
        await callback.answer("❌ Не удалось удалить фото", show_alert=True)

    await callback.answer()


@router.callback_query(F.data == "back_to_photos")
async def cb_back_to_photos(callback: CallbackQuery, api_client: APIClient):
    """Возврат к списку фото."""
    telegram_id = callback.from_user.id

    try:
        photos = await api_client.get_photos(telegram_id)
        if photos:
            await _send_photos_gallery(callback.message, photos, api_client)
        else:
            await callback.message.answer(
                "📸 У тебя пока нет фото.",
                reply_markup=profile_menu_keyboard(),
            )
    except Exception as e:
        logger.error(f"[Photos] Ошибка возврата к списку фото: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

    await callback.answer()
