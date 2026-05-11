"""
Утилиты для публикации событий в RabbitMQ.

Реализует publisher для 4 типов событий:
1. Swipe events (swipe.like, swipe.pass, swipe.super_like)
2. Match events (match.created)
3. Rating updates (rating.primary, rating.behavioral, rating.combined)
4. Chat messages (message.sent)
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

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

    EXCHANGE_DEFINITIONS = {
        "swipe": ("swipe_events", ExchangeType.TOPIC),
        "match": ("match_events", ExchangeType.TOPIC),
        "rating": ("rating_updates", ExchangeType.TOPIC),
        "chat": ("chat_messages", ExchangeType.TOPIC),
        "dlx": ("dlx", ExchangeType.TOPIC),
    }

    # Аргументы должны совпадать с infrastructure/rabbitmq/definitions.json,
    # иначе RabbitMQ откажет в повторной декларации очереди.
    QUEUE_DEFINITIONS = {
        "swipe_processing": {
            "durable": True,
            "arguments": {
                "x-message-ttl": 60000,
                "x-max-length": 10000,
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "swipe_processing.dlq",
            },
        },
        "match_notifications": {
            "durable": True,
            "arguments": {
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "match_notifications.dlq",
            },
        },
        "rating_calculation": {
            "durable": True,
            "arguments": {
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "rating_calculation.dlq",
            },
        },
        "message_delivery": {
            "durable": True,
            "arguments": {
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "message_delivery.dlq",
            },
        },
        "swipe_processing.dlq": {"durable": True, "arguments": {}},
        "match_notifications.dlq": {"durable": True, "arguments": {}},
        "rating_calculation.dlq": {"durable": True, "arguments": {}},
        "message_delivery.dlq": {"durable": True, "arguments": {}},
    }

    BINDINGS = (
        ("swipe", "swipe_processing", "swipe.*"),
        ("match", "match_notifications", "match.created"),
        ("rating", "rating_calculation", "rating.*"),
        ("chat", "message_delivery", "message.sent"),
        ("dlx", "swipe_processing.dlq", "swipe_processing.dlq"),
        ("dlx", "match_notifications.dlq", "match_notifications.dlq"),
        ("dlx", "rating_calculation.dlq", "rating_calculation.dlq"),
        ("dlx", "message_delivery.dlq", "message_delivery.dlq"),
    )

    VALID_SWIPE_ACTIONS = {"like", "pass", "super_like"}
    VALID_RATING_TYPES = {"primary", "behavioral", "combined"}

    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.channel = None
        self.exchanges = {}
        self._topology_declared = False

    async def connect(self):
        """Подключение к RabbitMQ.

        Использует `aio_pika.connect_robust` — клиент сам переподключается
        при обрыве. Топология (exchanges/queues/bindings) декларируется
        **один раз** на первом подключении; дальше горячий путь только
        publish'ит сообщения.
        """
        if self.connection and not self.connection.is_closed:
            return
        self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=100)

        # Exchanges нужно получить в self.exchanges всегда (после reconnect
        # экземпляры aio_pika уже знают, что декларация была — passive=True
        # сэкономит RTT).
        for name, (exchange_name, exchange_type) in self.EXCHANGE_DEFINITIONS.items():
            self.exchanges[name] = await self.channel.declare_exchange(
                exchange_name,
                exchange_type,
                durable=True,
                passive=self._topology_declared,
            )

        if not self._topology_declared:
            queues = {}
            for queue_name, options in self.QUEUE_DEFINITIONS.items():
                queues[queue_name] = await self.channel.declare_queue(
                    queue_name,
                    durable=options["durable"],
                    arguments=options["arguments"],
                )

            for exchange_key, queue_name, routing_key in self.BINDINGS:
                await queues[queue_name].bind(
                    self.exchanges[exchange_key],
                    routing_key=routing_key,
                )
            self._topology_declared = True

    async def publish_swipe_event(
        self,
        from_user_id: Any,
        to_user_id: Any,
        action: str,
        session_id: str = None,
        time_spent_ms: int = None,
        swipe_id: Any = None,
    ):
        """
        Опубликовать событие свайпа.
        
        Args:
            from_user_id: Кто свайпнул
            to_user_id: Кого свайпнули
            action: like, pass, super_like
            session_id: ID сессии
            time_spent_ms: Время просмотра анкеты
            swipe_id: ID записанного свайпа
        """
        if action not in self.VALID_SWIPE_ACTIONS:
            raise ValueError(f"Unsupported swipe action: {action}")

        event = {
            "event_id": str(uuid4()),
            "from_user_id": str(from_user_id),
            "to_user_id": str(to_user_id),
            "action": action,
            "session_id": session_id,
            "time_spent_ms": time_spent_ms,
            "swipe_id": str(swipe_id) if swipe_id is not None else None,
            "timestamp": self._utc_timestamp(),
        }

        routing_key = f"swipe.{action}"
        await self._publish("swipe", routing_key, event)

    async def publish_match_event(
        self,
        user1_id: Any,
        user2_id: Any,
        match_id: Any,
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
            "event_id": str(uuid4()),
            "user1_id": str(user1_id),
            "user2_id": str(user2_id),
            "match_id": str(match_id),
            "swipe_ids": [str(swipe_id) for swipe_id in (swipe_ids or [])],
            "timestamp": self._utc_timestamp(),
        }

        await self._publish("match", "match.created", event)

    async def publish_rating_update(
        self,
        user_id: Any,
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
        if rating_type not in self.VALID_RATING_TYPES:
            raise ValueError(f"Unsupported rating type: {rating_type}")

        event = {
            "event_id": str(uuid4()),
            "user_id": str(user_id),
            "rating_type": rating_type,
            "new_score": new_score,
            "old_score": old_score,
            "timestamp": self._utc_timestamp(),
        }

        routing_key = f"rating.{rating_type}"
        await self._publish("rating", routing_key, event)

    async def publish_message_sent(
        self,
        match_id: Any,
        sender_id: Any,
        message_id: Any,
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
            "event_id": str(uuid4()),
            "match_id": str(match_id),
            "sender_id": str(sender_id),
            "message_id": str(message_id),
            "content_preview": content_preview,
            "timestamp": self._utc_timestamp(),
        }

        await self._publish("chat", "message.sent", event)

    async def _publish(
        self,
        exchange_name: str,
        routing_key: str,
        event_data: Dict[str, Any]
    ):
        """Горячий путь публикации события — без declare-операций.

        Если соединение упало между запросами, `connect_robust` восстановит
        его лениво при первом обращении к exchange. Топология не
        пере-декларируется (см. флаг _topology_declared).
        """
        if not self.connection or self.connection.is_closed:
            await self.connect()

        exchange = self.exchanges[exchange_name]
        event_id = event_data.get("event_id")
        
        message = Message(
            body=json.dumps(event_data, default=str).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            message_id=event_id,
            timestamp=datetime.now(timezone.utc),
            headers={
                "source": "connectme-backend",
                "event_type": routing_key,
                "event_id": event_id,
            }
        )
        
        await exchange.publish(message, routing_key=routing_key)

    async def close(self):
        """Закрытие соединения."""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()

    @staticmethod
    def _utc_timestamp() -> str:
        """ISO timestamp в UTC для event payload."""
        return datetime.now(timezone.utc).isoformat()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
