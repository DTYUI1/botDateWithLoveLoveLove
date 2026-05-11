"""Базовый RabbitMQ-consumer с retry / DLQ / graceful shutdown.

Использование (наследник):

    class SwipeConsumer(BaseConsumer):
        queue_name = "swipe_processing"
        dlq_name = "swipe_processing.dlq"
        max_retries = 3

        async def handle(self, payload: dict, headers: dict) -> None:
            ...  # бизнес-логика

    async def main():
        consumer = SwipeConsumer(rabbitmq_url=settings.rabbitmq_url)
        await consumer.run_forever()

Особенности:

* `connect_robust` — авто-reconnect при обрыве.
* `ack-after-process`: ack только после успешной обработки; при исключении —
  `nack(requeue=False)` чтобы сообщение ушло в DLX/DLQ (см. definitions.json).
* Retries по счётчику в headers — после `max_retries` сообщение уходит в DLQ.
* Graceful shutdown по SIGTERM/SIGINT: stop консьюминг, дожидаемся текущих
  обработчиков, закрываем соединение.
"""

from __future__ import annotations

import asyncio
import json
import signal
from typing import Any, Dict

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from loguru import logger


class BaseConsumer:
    queue_name: str = ""
    dlq_name: str = ""
    prefetch_count: int = 32
    max_retries: int = 3
    requeue_delay_ms: int = 5000

    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None
        self._queue: aio_pika.abc.AbstractRobustQueue | None = None
        self._stop = asyncio.Event()

    async def handle(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> None:
        raise NotImplementedError

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        retries = int((message.headers or {}).get("x-retries", 0))
        log = logger.bind(
            queue=self.queue_name,
            message_id=message.message_id,
            retries=retries,
        )
        try:
            payload = json.loads(message.body)
        except json.JSONDecodeError as e:
            log.error(f"[Consumer] невалидный JSON, отбрасываем в DLQ: {e}")
            await message.nack(requeue=False)
            return

        try:
            await self.handle(payload, dict(message.headers or {}))
            await message.ack()
        except Exception as e:
            log.warning(f"[Consumer] handler упал: {type(e).__name__}: {e}")
            if retries + 1 >= self.max_retries:
                log.error("[Consumer] max_retries исчерпан, отправляем в DLQ")
                await message.nack(requeue=False)
                return
            # RabbitMQ requeue сохраняет исходные headers, поэтому retry-счётчик
            # обновляем через republish в ту же очередь и ack исходного сообщения.
            await asyncio.sleep(self.requeue_delay_ms / 1000)
            await self._republish_for_retry(message, retries + 1)
            await message.ack()

    async def _republish_for_retry(
        self,
        message: AbstractIncomingMessage,
        retries: int,
    ) -> None:
        if self._channel is None:
            raise RuntimeError("RabbitMQ channel is not initialized")
        headers = dict(message.headers or {})
        headers["x-retries"] = retries
        retry_message = aio_pika.Message(
            body=message.body,
            content_type=message.content_type,
            delivery_mode=message.delivery_mode,
            headers=headers,
            message_id=message.message_id,
            correlation_id=message.correlation_id,
            timestamp=message.timestamp,
        )
        await self._channel.default_exchange.publish(
            retry_message,
            routing_key=self.queue_name,
        )

    async def _connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self.prefetch_count)
        # Очередь уже задекларирована через definitions.json — берём пассивно.
        self._queue = await self._channel.declare_queue(self.queue_name, passive=True)
        logger.info(f"[Consumer:{self.queue_name}] подключён")

    async def run_forever(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._stop.set)
            except NotImplementedError:
                pass

        await self._connect()
        # Ручной ack/nack (без message.process), потому что нам нужен
        # контроль над retry-счётчиком и решением «requeue / в DLQ».
        async with self._queue.iterator(no_ack=False) as it:
            async for message in it:
                if self._stop.is_set():
                    break
                await self._on_message(message)
                if self._stop.is_set():
                    break

        logger.info(f"[Consumer:{self.queue_name}] graceful shutdown")
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
