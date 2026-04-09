"""
Обработчик команды /start и регистрации.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from keyboards.inline import start_keyboard, profile_menu_keyboard
from states import ProfileStates
from api_client import APIClient

router = Router()


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext, api_client: APIClient):
    """Обработка команды /start."""
    logger.info(f"📩 ВХОД в /start от user_id={message.from_user.id}, username={message.from_user.username}")
    telegram_id = message.from_user.id

    # Проверяем, есть ли профиль
    logger.debug(f"[start] Запрос профиля для telegram_id={telegram_id}")
    try:
        profile = await api_client.get_profile(telegram_id)
        logger.info(f"[start] Профиль получен: {'НАЙДЕН' if profile else 'НЕТ'}")
    except Exception as e:
        logger.error(f"[start] ОШИБКА get_profile: {type(e).__name__}: {e}")
        await message.answer(f"⚠️ Ошибка при загрузке профиля: {e}")
        return

    if profile:
        # Пользователь уже зарегистрирован
        logger.info(f"[start] Пользователь найден: {profile.get('display_name', 'N/A')}")
        try:
            await message.answer(
                f"👋 Привет, {profile.get('display_name', message.from_user.first_name)}!\n\n"
                "Рада видеть тебя снова! Что хочешь сделать?",
                reply_markup=profile_menu_keyboard(),
            )
            logger.info("✅ Ответ 'приветствие' отправлен")
        except Exception as e:
            logger.error(f"[start] ОШИБКА отправки ответа: {e}")
    else:
        # Новый пользователь
        logger.info(f"[start] Новый пользователь, показываю регистрацию")
        try:
            await message.answer(
                f"💕 Добро пожаловать в ConnectMe, {message.from_user.first_name}!\n\n"
                "Я помогу тебе найти интересного собеседника. "
                "Давай начнём с создания анкеты!\n\n"
                "Нажми кнопку ниже, чтобы создать профиль.",
                reply_markup=start_keyboard(),
            )
            logger.info("✅ Ответ 'регистрация' отправлен")
        except Exception as e:
            logger.error(f"[start] ОШИБКА отправки ответа: {e}")


@router.callback_query(F.data == "create_profile")
async def cb_create_profile(callback: CallbackQuery, state: FSMContext):
    """Начало создания профиля."""
    await callback.message.edit_text(
        "📝 Отлично! Давай создадим твою анкету.\n\n"
        "Сначала расскажи о себе. Как тебя зовут?"
    )
    await state.set_state(ProfileStates.waiting_for_name)
    await callback.answer()


@router.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery):
    """Информация о боте."""
    await callback.message.edit_text(
        "💕 <b>ConnectMe</b> — умные знакомства для осознанных пользователей.\n\n"
        "Я помогу тебе:\n"
        "• Создать подробную анкету\n"
        "• Найти подходящие пары по интересам\n"
        "• Получить идеи для свиданий\n\n"
        "Используй команды:\n"
        "/start — начать\n"
        "/profile — мой профиль\n"
        "/search — поиск анкет\n"
        "/matches — мои мэтчи\n"
        "/settings — настройки",
    )
    await callback.answer()
