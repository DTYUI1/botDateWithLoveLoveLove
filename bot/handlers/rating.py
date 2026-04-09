"""
Обработчики для просмотра рейтинга пользователя.
"""

from aiogram import Router, F
from aiogram.types import Message
from loguru import logger

from api_client import APIClient

router = Router()


# Маппинг tier на эмодзи и описание
TIER_INFO = {
    "S": {"emoji": "👑", "name": "Элита", "desc": "Топ-10% пользователей"},
    "A": {"emoji": "💎", "name": "Отличный", "desc": "Топ-25% пользователей"},
    "B": {"emoji": "⭐", "name": "Хороший", "desc": "Топ-40% пользователей"},
    "C": {"emoji": "✨", "name": "Средний", "desc": "Выше среднего"},
    "D": {"emoji": "🌱", "name": "Начинающий", "desc": "Есть куда расти"},
    "E": {"emoji": "🆕", "name": "Новый", "desc": "Заполни профиль для рейтинга"},
}


@router.message(F.text == "/rating")
async def cmd_rating(message: Message, api_client: APIClient):
    """Показать рейтинг пользователя."""
    telegram_id = message.from_user.id
    logger.info(f"[Bot Rating] /rating от user_id={telegram_id}")

    # Проверяем, есть ли профиль
    profile = await api_client.get_profile(telegram_id)
    if not profile:
        await message.answer(
            "📝 Сначала создай анкету! Нажми /start чтобы начать."
        )
        return

    try:
        # Получаем рейтинг
        rating_data = await api_client.get_rating(telegram_id)

        if not rating_data:
            await message.answer(
                "📊 Твой рейтинг ещё рассчитывается.\n\n"
                "Заполни профиль полностью, чтобы получить максимальный балл!"
            )
            return

        total_score = rating_data.get("total_score", 0.0)
        tier = rating_data.get("tier", "E")
        percentile = rating_data.get("percentile")
        rank_position = rating_data.get("rank_position")

        # Информация о tier
        tier_info = TIER_INFO.get(tier, TIER_INFO["E"])
        tier_emoji = tier_info["emoji"]
        tier_name = tier_info["name"]
        tier_desc = tier_info["desc"]

        # Формируем текст
        score_pct = int(total_score * 100)
        
        # Прогресс-бар
        progress = "▓" * (score_pct // 10) + "░" * (10 - score_pct // 10)
        
        rating_text = (
            f"{tier_emoji} <b>Твой рейтинг: {tier_name}</b>\n"
            f"📊 {tier_desc}\n\n"
            f"📈 Общий балл: <b>{score_pct}%</b>\n"
            f" [{progress}]\n\n"
            f"📋 Детали:\n"
            f"• Заполненность профиля: {int(rating_data.get('primary_score', 0) * 100)}%\n"
            f"• Активность: {int(rating_data.get('behavioral_score', 0) * 100)}%\n"
        )

        if rank_position:
            rating_text += f"• Позиция в рейтинге: #{rank_position}\n"
        
        if percentile:
            percentile_pct = int(percentile * 100)
            rating_text += f"• Ты лучше, чем {percentile_pct}% пользователей\n"

        rating_text += (
            "\n💡 <b>Как повысить рейтинг:</b>\n"
            "• Заполни все поля профиля\n"
            "• Добавь качественные фото\n"
            "• Пройди верификацию\n"
            "• Будь активнее в поиске"
        )

        await message.answer(rating_text)

    except Exception as e:
        logger.error(f"[Bot Rating] Ошибка получения рейтинга: {e}")
        await message.answer(
            "❌ Не удалось загрузить рейтинг. Попробуй позже."
        )
