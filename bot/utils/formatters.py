"""Форматирование данных профиля для Telegram-сообщений."""

from typing import Optional

GENDER_RU = {
    "male": "Мужской",
    "female": "Женский",
    "other": "Другой",
}

LOOKING_FOR_RU = {
    "male": "Парней",
    "female": "Девушек",
    "both": "Всех",
}


def gender_ru(value: Optional[str]) -> str:
    if not value:
        return "не указан"
    return GENDER_RU.get(value, value)


def looking_for_ru(value: Optional[str]) -> str:
    if not value:
        return "не указано"
    return LOOKING_FOR_RU.get(value, value)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_profile_card(profile: dict, *, max_length: int = 950) -> str:
    """Карточка анкеты для свайпа (caption под фото, до ~1024 символов).

    Не выводит пол/looking_for — это поля смотрящего, а не показываемого.
    """
    name = profile.get("display_name") or "Аноним"
    age = profile.get("age")
    city = profile.get("city") or "не указан"
    bio = (profile.get("bio") or "").strip()
    interests = ", ".join(profile.get("interests") or [])

    age_str = f", {age}" if age else ""
    text = f"<b>{name}{age_str}</b>\n📍 {city}"
    if bio:
        text += f"\n\n📝 {bio}"
    if interests:
        text += f"\n\n🎯 {interests}"

    return _truncate(text, max_length)


def format_own_profile(profile: dict) -> str:
    """Полная карточка собственного профиля — с полом и looking_for на русском."""
    name = profile.get("display_name") or "Аноним"
    age = profile.get("age", "не указан")
    city = profile.get("city") or "не указан"
    bio = profile.get("bio") or "не указано"
    interests = ", ".join(profile.get("interests") or []) or "не указаны"

    return (
        f"👤 <b>{name}</b>\n"
        f"🎂 Возраст: {age}\n"
        f"⚧ Пол: {gender_ru(profile.get('gender'))}\n"
        f"📍 Город: {city}\n"
        f"💕 Ищу: {looking_for_ru(profile.get('looking_for'))}\n\n"
        f"📝 О себе: {bio}\n\n"
        f"🎯 Интересы: {interests}"
    )


def format_match_line(match_profile: dict) -> str:
    """Строка для списка мэтчей."""
    name = match_profile.get("display_name") or "Аноним"
    age = match_profile.get("age")
    city = match_profile.get("city")

    line = f"👤 {name}"
    if age:
        line += f", {age}"
    if city:
        line += f", {city}"
    return line
