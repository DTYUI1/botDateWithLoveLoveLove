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

    # RabbitMQ (для consumer'ов уведомлений)
    rabbitmq_url: str = "amqp://REQUIRED_RABBITMQ_USER:REQUIRED_RABBITMQ_PASSWORD@rabbitmq:5672//"

    # /metrics endpoint бота
    metrics_host: str = "0.0.0.0"
    metrics_port: int = 8001

    # Логирование
    log_level: str = "INFO"


settings = BotSettings()
