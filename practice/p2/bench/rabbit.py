import asyncio
import time

import aio_pika

from bench import config
from bench.message import build_message, read_sent_at
from bench.metrics import RunMetrics


async def connect() -> aio_pika.abc.AbstractRobustConnection:
    return await aio_pika.connect_robust(
        host=config.RABBITMQ_HOST,
        port=config.RABBITMQ_PORT,
        login=config.RABBITMQ_USER,
        password=config.RABBITMQ_PASSWORD,
    )


async def purge() -> None:
    conn = await connect()
    try:
        ch = await conn.channel()
        queue = await ch.declare_queue(config.RABBITMQ_QUEUE, durable=True)
        await queue.purge()
    finally:
        await conn.close()


async def producer(rate: int, size: int, metrics: RunMetrics, stop: asyncio.Event) -> None:
    conn = await connect()
    try:
        ch = await conn.channel(publisher_confirms=False)
        await ch.declare_queue(config.RABBITMQ_QUEUE, durable=True)
        exchange = ch.default_exchange

        interval = 1.0 / rate
        msg_id = 0
        next_send = time.perf_counter()

        while not stop.is_set():
            try:
                body = build_message(msg_id, size)
                await exchange.publish(
                    aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT),
                    routing_key=config.RABBITMQ_QUEUE,
                )
                metrics.sent += 1
                msg_id += 1
            except Exception:
                metrics.errors += 1

            next_send += interval
            sleep_for = next_send - time.perf_counter()
            if sleep_for > 0:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=sleep_for)
                except asyncio.TimeoutError:
                    pass
    finally:
        await conn.close()


async def consumer(metrics: RunMetrics, stop: asyncio.Event) -> None:
    conn = await connect()
    try:
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=1000)
        queue = await ch.declare_queue(config.RABBITMQ_QUEUE, durable=True)

        async with queue.iterator() as it:
            async for message in it:
                async with message.process(ignore_processed=True):
                    try:
                        sent_at = read_sent_at(message.body)
                        metrics.record_latency(sent_at, time.time())
                    except Exception:
                        metrics.errors += 1
                if stop.is_set():
                    break
    finally:
        await conn.close()


async def queue_size() -> int:
    conn = await connect()
    try:
        ch = await conn.channel()
        queue = await ch.declare_queue(config.RABBITMQ_QUEUE, durable=True, passive=True)
        return queue.declaration_result.message_count or 0
    finally:
        await conn.close()
