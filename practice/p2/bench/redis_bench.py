import asyncio
import time

import redis.asyncio as redis

from bench import config
from bench.message import build_message, read_sent_at
from bench.metrics import RunMetrics


def _client() -> redis.Redis:
    return redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=False)


async def purge() -> None:
    r = _client()
    try:
        await r.delete(config.REDIS_QUEUE)
    finally:
        await r.aclose()


async def producer(rate: int, size: int, metrics: RunMetrics, stop: asyncio.Event) -> None:
    r = _client()
    try:
        interval = 1.0 / rate
        msg_id = 0
        next_send = time.perf_counter()

        while not stop.is_set():
            try:
                body = build_message(msg_id, size)
                await r.rpush(config.REDIS_QUEUE, body)
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
        await r.aclose()


async def consumer(metrics: RunMetrics, stop: asyncio.Event) -> None:
    r = _client()
    try:
        while not stop.is_set():
            try:
                item = await r.blpop(config.REDIS_QUEUE, timeout=1)
                if item is None:
                    continue
                _key, raw = item
                sent_at = read_sent_at(raw)
                metrics.record_latency(sent_at, time.time())
            except Exception:
                metrics.errors += 1
    finally:
        await r.aclose()


async def queue_size() -> int:
    r = _client()
    try:
        return int(await r.llen(config.REDIS_QUEUE))
    finally:
        await r.aclose()
