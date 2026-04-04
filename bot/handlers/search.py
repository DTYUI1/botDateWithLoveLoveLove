"""
Обработчики поиска анкет и свайпов.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.keyboards.inline import swipe_keyboard
from bot.states import SearchStates
from bot.api_client import APIClient

router = Router()


@router.message(F.text == "/search")
async def cmd_search(message: Message, state: FSMContext, api_client: APIClient):
    """Начать поиск анкет."""
    telegram_id = message.from_user.id

    # Проверяем, есть ли профиль
    profile = await api_client.get_profile(telegram_id)
    if not profile:
        await message.answer(
            "📝 Сначала создай анкету! Нажми /start чтобы начать."
        )
        return

    await message.answer("🔍 Ищу подходящую анкету для тебя...")
    await show_next_profile(message, state, api_client, telegram_id)


async def show_next_profile(
    message: Message,
    state: FSMContext,
    api_client: APIClient,
    telegram_id: int,
):
    """Показывает следующую анкету."""
    profile = await api_client.get_next_profile(telegram_id)

    if not profile:
        await message.answer(
            "😔 Пока нет подходящих анкет.\n\n"
            "Попробуй позже или измени настройки поиска.\n"
            "Используй /settings для изменения предпочтений."
        )
        return

    # Формируем текст анкеты
    interests = ", ".join(profile.get("interests", []))
    profile_text = (
        f"👤 <b>{profile.get('display_name', 'Аноним')}</b>\n"
        f"🎂 Возраст: {profile.get('age', 'не указан')}\n"
        f"📍 Город: {profile.get('city', 'не указан')}\n\n"
        f"📝 {profile.get('bio', 'нет описания')}\n\n"
        f"🎯 Интересы: {interests if interests else 'не указаны'}"
    )

    await state.update_data(
        current_profile_id=profile.get("id"),
        current_profile_data=profile,
    )
    await state.set_state(SearchStates.viewing_profile)

    await message.answer(profile_text, reply_markup=swipe_keyboard())


@router.callback_query(F.data == "swipe_like", SearchStates.viewing_profile)
async def cb_swipe_like(callback: CallbackQuery, state: FSMContext, api_client: APIClient):
    """Лайк анкеты."""
    telegram_id = callback.from_user.id
    data = await state.get_data()
    profile_id = data.get("current_profile_id")

    if not profile_id:
        await callback.answer("❌ Ошибка: профиль не найден", show_alert=True)
        return

    try:
        result = await api_client.swipe(telegram_id, profile_id, "like")

        if result.get("is_match"):
            # Произошёл мэтч!
            await callback.message.answer(
                "🎉 У вас мэтч!\n\n"
                f"Вы понравились друг другу с {result.get('match_profile_name', 'пользователем')}.\n"
                "Теперь вы можете начать общение! 💬"
            )
        else:
            await callback.message.answer("❤️ Лайк отправлен!")
            await show_next_profile(callback.message, state, api_client, telegram_id)

    except Exception as e:
        logger.error(f"Ошибка свайпа: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуй позже.", show_alert=True)

    await callback.answer()


@router.callback_query(F.data == "swipe_pass", SearchStates.viewing_profile)
async def cb_swipe_pass(callback: CallbackQuery, state: FSMContext, api_client: APIClient):
    """Пропуск анкеты."""
    telegram_id = callback.from_user.id
    data = await state.get_data()
    profile_id = data.get("current_profile_id")

    if not profile_id:
        await callback.answer("❌ Ошибка: профиль не найден", show_alert=True)
        return

    try:
        await api_client.swipe(telegram_id, profile_id, "pass")
        await callback.message.answer("❌ Пропущено!")
        await show_next_profile(callback.message, state, api_client, telegram_id)
    except Exception as e:
        logger.error(f"Ошибка свайпа: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуй позже.", show_alert=True)

    await callback.answer()


@router.callback_query(F.data == "start_search")
async def cb_start_search(callback: CallbackQuery, state: FSMContext, api_client: APIClient):
    """Начать поиск из меню профиля."""
    telegram_id = callback.from_user.id
    await callback.message.edit_text("🔍 Ищу подходящую анкету для тебя...")
    await show_next_profile(callback.message, state, api_client, telegram_id)
    await callback.answer()
