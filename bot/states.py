"""
FSM состояния для Telegram бота ConnectMe.
"""

from aiogram.fsm.state import State, StatesGroup


class ProfileStates(StatesGroup):
    """Состояния для создания/редактирования профиля."""
    
    # Создание профиля
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_gender = State()
    waiting_for_bio = State()
    waiting_for_interests = State()
    waiting_for_city = State()
    waiting_for_looking_for = State()
    waiting_for_photo = State()
    
    # Редактирование профиля
    editing_name = State()
    editing_age = State()
    editing_gender = State()
    editing_bio = State()
    editing_interests = State()
    editing_city = State()
    editing_looking_for = State()


class SearchStates(StatesGroup):
    """Состояния для поиска анкет."""
    
    viewing_profile = State()
    waiting_for_message = State()
