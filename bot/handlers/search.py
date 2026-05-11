"""
Обработчики поиска анкет и свайпов.

Интеграция с backend:
- Сохранение session_id для использования Redis кэша
- Автоматический refresh сессии при окончании анкет
- Корректная обработка мэтчей
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from keyboards.inline import swipe_keyboard, match_chat_keyboard
from api_client import APIClient
from utils.formatters import format_profile_card

router = Router()


class SearchStates(StatesGroup):
    """Состояния для поиска анкет."""
    viewing_profile = State()


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
    await show_next_profile(message, state, api_client, telegram_id, refresh_session=True)


async def show_next_profile(
    message: Message,
    state: FSMContext,
    api_client: APIClient,
    telegram_id: int,
    refresh_session: bool = False,
):
    """Показывает следующую анкету.
    
    Args:
        message: Сообщение для отправки
        state: FSM контекст
        api_client: HTTP клиент
        telegram_id: Telegram ID пользователя
        refresh_session: Если True, обновить сессию при отсутствии анкет
    """
    # Получаем session_id из состояния
    data = await state.get_data()
    session_id = data.get("session_id")

    # Запрашиваем анкету
    profile = await api_client.get_next_profile(telegram_id, session_id=session_id)

    if not profile:
        # Анкеты закончились — пробуем refresh
        if refresh_session:
            await message.answer("😔 Анкеты закончились. Обновляю подборку...")
            try:
                refresh_result = await api_client.refresh_session(telegram_id, session_id)
                new_session_id = refresh_result.get("session_id")
                cached_count = refresh_result.get("cached_count", 0)

                if cached_count > 0:
                    # Сохраняем новый session_id
                    await state.update_data(session_id=new_session_id)
                    await message.answer(f"✅ Нашел ещё {cached_count} анкет!")
                    # Пробуем снова
                    await show_next_profile(message, state, api_client, telegram_id)
                    return
                else:
                    await message.answer(
                        "😔 Пока нет новых анкет.\n\n"
                        "Попробуй позже или измени настройки поиска.\n"
                        "Используй /settings для изменения предпочтений."
                    )
                    return
            except Exception as e:
                logger.error(f"[Search] Ошибка refresh сессии: {e}")
                await message.answer(
                    "😔 Пока нет подходящих анкет.\n\n"
                    "Попробуй позже или измени настройки поиска."
                )
                return
        else:
            await message.answer(
                "😔 Пока нет подходящих анкет.\n\n"
                "Попробуй позже или измени настройки поиска.\n"
                "Используй /settings для изменения предпочтений."
            )
            return

    # Если это первая анкета из новой сессии — сохраняем session_id
    if not session_id:
        # Backend может вернуть session_id в ответе refresh, но get_next_profile его не возвращает
        # Поэтому session_id остаётся None до первого refresh или явно создаётся backend
        logger.debug("[Search] Анкета получена без session_id")

    # Если в ответе есть session_id (например, после refresh) — сохраняем
    if isinstance(profile, dict) and profile.get("session_id"):
        await state.update_data(session_id=profile["session_id"])

    # Формируем текст анкеты
    profile_text = format_profile_card(profile)
    photo_url = profile.get("primary_photo_url")

    await state.update_data(
        current_profile_id=str(profile.get("id")),
        current_profile_data=profile,
    )
    await state.set_state(SearchStates.viewing_profile)

    if photo_url:
        photo_bytes = await api_client.fetch_photo_bytes(photo_url)
        if photo_bytes:
            try:
                await message.answer_photo(
                    photo=BufferedInputFile(photo_bytes, filename="photo.jpg"),
                    caption=profile_text,
                    reply_markup=swipe_keyboard(),
                )
                return
            except Exception as e:
                logger.warning(f"[Search] Не удалось отправить фото: {e}. Падаю на текст.")

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
            match_name = result.get("match_profile_name") or "пользователем"
            match_username = result.get("match_username")
            tail = (
                "Нажми кнопку ниже, чтобы написать в Telegram."
                if match_username
                else "К сожалению, у партнёра не указан @username — написать напрямую не получится."
            )
            await callback.message.answer(
                f"🎉 <b>У вас мэтч с {match_name}!</b>\n\n{tail}",
                reply_markup=match_chat_keyboard(match_username),
            )
        else:
            await callback.answer("❤️")
            # Показываем следующую анкету
            await show_next_profile(callback.message, state, api_client, telegram_id)
            return  # Не отправляем дополнительное сообщение

    except Exception as e:
        logger.error(f"[Search] Ошибка свайпа: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуй позже.", show_alert=True)
        return

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
        await callback.answer("❌")
        # Показываем следующую анкету
        await show_next_profile(callback.message, state, api_client, telegram_id)
        return  # Не отправляем дополнительное сообщение

    except Exception as e:
        logger.error(f"[Search] Ошибка свайпа: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуй позже.", show_alert=True)
        return

    await callback.answer()


@router.callback_query(F.data == "start_search")
async def cb_start_search(callback: CallbackQuery, state: FSMContext, api_client: APIClient):
    """Начать поиск из меню профиля."""
    telegram_id = callback.from_user.id
    await callback.message.edit_text("🔍 Ищу подходящую анкету для тебя...")
    await show_next_profile(callback.message, state, api_client, telegram_id, refresh_session=True)
    await callback.answer()
