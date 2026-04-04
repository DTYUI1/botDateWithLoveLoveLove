"""
Конфигурация Telegram Bot Service.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str

    # Backend
    backend_url: str = "http://localhost:8005"

    # Логирование
    log_level: str = "INFO"


settings = BotSettings()
