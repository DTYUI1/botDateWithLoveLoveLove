"""
Общие обработчики: /cancel и другие утилиты.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from loguru import logger

router = Router()


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
