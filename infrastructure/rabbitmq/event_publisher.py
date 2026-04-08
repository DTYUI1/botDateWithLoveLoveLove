"""
Утилиты для публикации событий в RabbitMQ.

Реализует publisher для 4 типов событий:
1. Swipe events (swipe.like, swipe.pass, swipe.super_like)
2. Match events (match.created)
3. Rating updates (rating.primary, rating.behavioral, rating.combined)
4. Chat messages (message.sent)
"""

import json
from typing import Dict, Any
from datetime import datetime

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType


class EventPublisher:
    """
    Универсальный publisher событий в RabbitMQ.
    
    Поддерживает 4 exchange:
    - swipe_events (topic)
    - match_events (topic)
    - rating_updates (topic)
    - chat_messages (topic)
    """

    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.channel = None
        self.exchanges = {}

    async def connect(self):
        """Подключение к RabbitMQ и получение exchanges."""
        self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()

        # Объявить exchanges
        exchange_definitions = {
            "swipe": ("swipe_events", ExchangeType.TOPIC),
            "match": ("match_events", ExchangeType.TOPIC),
            "rating": ("rating_updates", ExchangeType.TOPIC),
            "chat": ("chat_messages", ExchangeType.TOPIC),
        }

        for name, (exchange_name, exchange_type) in exchange_definitions.items():
            self.exchanges[name] = await self.channel.declare_exchange(
                exchange_name,
                exchange_type,
                durable=True
            )

    async def publish_swipe_event(
        self,
        from_user_id: int,
        to_user_id: int,
        action: str,
        session_id: str = None,
        time_spent_ms: int = None
    ):
        """
        Опубликовать событие свайпа.
        
        Args:
            from_user_id: Кто свайпнул
            to_user_id: Кого свайпнули
            action: like, pass, super_like
            session_id: ID сессии
            time_spent_ms: Время просмотра анкеты
        """
        event = {
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "action": action,
            "session_id": session_id,
            "time_spent_ms": time_spent_ms,
            "timestamp": datetime.utcnow().isoformat()
        }

        routing_key = f"swipe.{action}"
        await self._publish("swipe", routing_key, event)

    async def publish_match_event(
        self,
        user1_id: int,
        user2_id: int,
        match_id: int,
        swipe_ids: list = None
    ):
        """
        Опубликовать событие мэтча.
        
        Args:
            user1_id: ID первого пользователя
            user2_id: ID второго пользователя
            match_id: ID мэтча
            swipe_ids: ID свайпов
        """
        event = {
            "user1_id": user1_id,
            "user2_id": user2_id,
            "match_id": match_id,
            "swipe_ids": swipe_ids or [],
            "timestamp": datetime.utcnow().isoformat()
        }

        await self._publish("match", "match.created", event)

    async def publish_rating_update(
        self,
        user_id: int,
        rating_type: str,
        new_score: float,
        old_score: float = None
    ):
        """
        Опубликовать событие обновления рейтинга.
        
        Args:
            user_id: ID пользователя
            rating_type: primary, behavioral, combined
            new_score: Новый score
            old_score: Предыдущий score
        """
        event = {
            "user_id": user_id,
            "rating_type": rating_type,
            "new_score": new_score,
            "old_score": old_score,
            "timestamp": datetime.utcnow().isoformat()
        }

        routing_key = f"rating.{rating_type}"
        await self._publish("rating", routing_key, event)

    async def publish_message_sent(
        self,
        match_id: int,
        sender_id: int,
        message_id: int,
        content_preview: str = None
    ):
        """
        Опубликовать событие отправки сообщения.
        
        Args:
            match_id: ID мэтча
            sender_id: ID отправителя
            message_id: ID сообщения
            content_preview: Превью содержимого
        """
        event = {
            "match_id": match_id,
            "sender_id": sender_id,
            "message_id": message_id,
            "content_preview": content_preview,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self._publish("chat", "message.sent", event)

    async def _publish(
        self,
        exchange_name: str,
        routing_key: str,
        event_data: Dict[str, Any]
    ):
        """Внутренний метод публикации события."""
        if not self.connection or self.connection.is_closed:
            await self.connect()

        exchange = self.exchanges[exchange_name]
        
        message = Message(
            body=json.dumps(event_data, default=str).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers={
                "source": "connectme-backend",
                "event_type": routing_key
            }
        )
        
        await exchange.publish(message, routing_key=routing_key)

    async def close(self):
        """Закрытие соединения."""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
