"""
Общие обработчики: /cancel и другие утилиты.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

router = Router()
fallback_router = Router()


@router.message(F.text == "/cancel")
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущего FSM диалога."""
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer("ℹ️ Нет активных диалогов для отмены.")
        return

    await state.clear()
    logger.info(f"[Cancel] Пользователь {message.from_user.id} отменил диалог (было: {current_state})")
    
    await message.answer(
        "❌ Диалог отменён.\n\n"
        "Используй меню для навигации:"
    )


@router.callback_query(F.data == "open_chat")
async def cb_open_chat(callback: CallbackQuery):
    """Заглушка для не реализованного чата."""
    await callback.answer("Чат с мэтчами пока не реализован.", show_alert=True)


@router.callback_query(F.data == "date_ideas")
async def cb_date_ideas(callback: CallbackQuery):
    """Заглушка для идей свиданий."""
    await callback.answer("Идеи для свиданий скоро появятся.", show_alert=True)


@router.callback_query(F.data.in_({"confirm_yes", "confirm_no"}))
async def cb_confirm_fallback(callback: CallbackQuery):
    """Безопасный ответ на устаревшие кнопки подтверждения."""
    await callback.answer("Это действие сейчас не поддерживается.")


@fallback_router.callback_query()
async def cb_unknown_callback(callback: CallbackQuery):
    """Страховочный обработчик для неизвестных callback-ов."""
    logger.warning(
        f"[Callbacks] Неизвестный callback от user_id={callback.from_user.id}: {callback.data!r}"
    )
    await callback.answer("Эта кнопка пока не поддерживается.")
