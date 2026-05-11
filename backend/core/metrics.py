"""Бизнес-метрики backend для Prometheus.

Метрики собирает уже подключённый `prometheus-fastapi-instrumentator` в
`main.py` (он отдаёт HTTP-метрики), а здесь — кастомные бизнес-показатели:
свайпы, мэтчи, кэш-хиты, ошибки публикации в RabbitMQ.

Использование:

    from core.metrics import (
        SWIPES_TOTAL, MATCHES_TOTAL, SWIPE_DURATION,
        CACHE_HITS, CACHE_MISSES, MQ_PUBLISH_ERRORS,
    )
    SWIPES_TOTAL.labels(action="like").inc()
"""

from prometheus_client import Counter, Histogram


SWIPES_TOTAL = Counter(
    "connectme_swipes_total",
    "Количество свайпов по действиям",
    ["action"],
)

MATCHES_TOTAL = Counter(
    "connectme_matches_total",
    "Количество созданных мэтчей",
)

SWIPE_DURATION = Histogram(
    "connectme_swipe_duration_seconds",
    "Время обработки одного свайпа (от запроса до записи в БД + publish)",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

CACHE_HITS = Counter(
    "connectme_cache_hits_total",
    "Кэш-хиты по типу кеша",
    ["cache"],
)

CACHE_MISSES = Counter(
    "connectme_cache_misses_total",
    "Кэш-миссы по типу кеша",
    ["cache"],
)

MQ_PUBLISH_ERRORS = Counter(
    "connectme_mq_publish_errors_total",
    "Ошибки публикации событий в RabbitMQ",
    ["op"],
)

MQ_PUBLISH_OK = Counter(
    "connectme_mq_publish_ok_total",
    "Успешные публикации событий в RabbitMQ",
    ["op"],
)
