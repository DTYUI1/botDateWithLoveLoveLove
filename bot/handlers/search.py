"""
Обработчики поиска анкет и свайпов.

Интеграция с backend:
- Сохранение session_id для использования Redis кэша
- Автоматический refresh сессии при окончании анкет
- Корректная обработка мэтчей

UX-правило: одна "карточка анкеты" — один редактируемый экран.
Свайпы заменяют текущую карточку следующей, а не плодят пачку сообщений.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from keyboards.inline import swipe_keyboard, match_chat_keyboard
from api_client import APIClient
from utils.formatters import format_profile_card
from utils.message_editor import edit_or_answer, replace_with_photo

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

    # Один статус-экран, который дальше будет редактироваться в карточку
    status_msg = await message.answer("🔍 Ищу подходящую анкету для тебя...")
    await show_next_profile(
        status_msg, state, api_client, telegram_id, refresh_session=True
    )


async def show_next_profile(
    screen: Message,
    state: FSMContext,
    api_client: APIClient,
    telegram_id: int,
    refresh_session: bool = False,
):
    """Показывает следующую анкету, редактируя переданный экран.

    Args:
        screen: Текущее сообщение-экран, которое надо обновить.
        state: FSM контекст.
        api_client: HTTP клиент.
        telegram_id: Telegram ID пользователя.
        refresh_session: Если True, обновить сессию при отсутствии анкет.
    """
    data = await state.get_data()
    session_id = data.get("session_id")

    # Запрашиваем анкету
    profile = await api_client.get_next_profile(telegram_id, session_id=session_id)

    if not profile:
        if refresh_session:
            await edit_or_answer(screen, "😔 Анкеты закончились. Обновляю подборку...")
            try:
                refresh_result = await api_client.refresh_session(telegram_id, session_id)
                new_session_id = refresh_result.get("session_id")
                cached_count = refresh_result.get("cached_count", 0)

                if cached_count > 0:
                    await state.update_data(session_id=new_session_id)
                    # Пробуем ещё раз на том же экране
                    await show_next_profile(screen, state, api_client, telegram_id)
                    return
                await edit_or_answer(
                    screen,
                    "😔 Пока нет новых анкет.\n\n"
                    "Попробуй позже или измени настройки поиска.\n"
                    "Используй /settings для изменения предпочтений.",
                )
                return
            except Exception as e:
                logger.error(f"[Search] Ошибка refresh сессии: {e}")
                await edit_or_answer(
                    screen,
                    "😔 Пока нет подходящих анкет.\n\n"
                    "Попробуй позже или измени настройки поиска.",
                )
                return
        else:
            await edit_or_answer(
                screen,
                "😔 Пока нет подходящих анкет.\n\n"
                "Попробуй позже или измени настройки поиска.\n"
                "Используй /settings для изменения предпочтений.",
            )
            return

    # Если backend вернул session_id — сохраняем
    if isinstance(profile, dict) and profile.get("session_id"):
        await state.update_data(session_id=profile["session_id"])

    profile_text = format_profile_card(profile)
    photo_url = profile.get("primary_photo_url")

    photo_bytes = None
    if photo_url:
        photo_bytes = await api_client.fetch_photo_bytes(photo_url)

    if photo_bytes:
        new_screen = await replace_with_photo(
            screen,
            photo_bytes=photo_bytes,
            caption=profile_text,
            reply_markup=swipe_keyboard(),
        )
    else:
        new_screen = await edit_or_answer(
            screen,
            profile_text,
            reply_markup=swipe_keyboard(),
        )

    await state.update_data(
        current_profile_id=str(profile.get("id")),
        current_profile_data=profile,
        search_screen_id=new_screen.message_id,
        search_screen_chat_id=new_screen.chat.id,
    )
    await state.set_state(SearchStates.viewing_profile)


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
            match_name = result.get("match_profile_name") or "пользователем"
            match_username = result.get("match_username")
            tail = (
                "Нажми кнопку ниже, чтобы написать в Telegram."
                if match_username
                else "К сожалению, у партнёра не указан @username — написать напрямую не получится."
            )
            await edit_or_answer(
                callback.message,
                f"🎉 <b>У вас мэтч с {match_name}!</b>\n\n{tail}",
                reply_markup=match_chat_keyboard(match_username),
            )
            await callback.answer("❤️")
            return

        await callback.answer("❤️")
        # Заменяем текущую карточку следующей на том же экране
        await show_next_profile(callback.message, state, api_client, telegram_id)
        return

    except Exception as e:
        logger.error(f"[Search] Ошибка свайпа: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуй позже.", show_alert=True)
        return


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
        # Заменяем текущую карточку следующей на том же экране
        await show_next_profile(callback.message, state, api_client, telegram_id)
        return

    except Exception as e:
        logger.error(f"[Search] Ошибка свайпа: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуй позже.", show_alert=True)
        return


@router.callback_query(F.data == "start_search")
async def cb_start_search(callback: CallbackQuery, state: FSMContext, api_client: APIClient):
    """Начать поиск из меню профиля — редактируем текущий экран в карточку."""
    telegram_id = callback.from_user.id
    await callback.answer()
    screen = await edit_or_answer(
        callback.message, "🔍 Ищу подходящую анкету для тебя..."
    )
    await show_next_profile(screen, state, api_client, telegram_id, refresh_session=True)
