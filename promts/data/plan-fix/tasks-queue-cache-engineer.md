# Задачи для Queue & Cache Engineer

**Промт агента:** `promts/queue_cache_engineer.md`
**Источник несоответствий:** `promts/data/plan-fix/plan-fix.md`
**Ветка:** `stage4`

## Контекст

Брокер RabbitMQ объявлен (4 exchange + 4 queue + bindings), MinIO работает, Redis-паттерны реализованы (ProfileSessionCache, RatingCache, SwipeCounterCache). НО:
- **0 consumer'ов** — события публикуются «в воздух», очереди копятся.
- `EventPublisher.connect()` объявляет всю топологию на **каждое** подключение, а соединение открывается на **каждый свайп** (`async with EventPublisher(...)` в `matching.py:189`).
- Celery использует Redis как broker — RabbitMQ под Celery не задействован.

Твоя задача — превратить «декларации очередей» в реально работающий брокер с пользой для системы.

---

## T-Q1. Рефактор EventPublisher: singleton + setup_topology (разделы 3.8, 3.9)

**Где:** `infrastructure/rabbitmq/event_publisher.py:67-92`.

**Что сделать:**
1. Разделить логику на две стадии:
   ```python
   class EventPublisher:
       async def setup_topology(self):
           """Выполняется ОДИН раз при старте приложения.
           Декларирует exchanges, queues, bindings."""

       async def connect(self):
           """Открывает robust-connection и channel. Без declare."""

       async def publish_swipe_event(...):
           """Горячий путь — только publish, без declare."""
   ```
2. В `backend/main.py` lifespan создать один долгоживущий `EventPublisher`, вызвать `setup_topology()` один раз, затем `connect()` и положить в `app.state.event_publisher`.
3. Использовать `aio_pika.connect_robust` с auto-reconnect.
4. Закрытие — на shutdown lifespan.
5. Декларации очередей и exchanges должны соответствовать `definitions.json` (durable, ttl, max-length).

**Acceptance:**
- Один свайп → 0 declare-операций (RabbitMQ Management UI: вкладка Channels → `messages.declare` не растёт).
- При перезапуске backend очереди не пересоздаются (durable).
- При падении RabbitMQ — robust-reconnect восстанавливает соединение, без рестарта backend.

**Приоритет:** средний. **Оценка:** 2–3 ч.

---

## T-Q2. Базовый фреймворк для consumer'ов (раздел 3.3)

**Файл:** `infrastructure/rabbitmq/base_consumer.py` (новый).

**Что сделать:**
- Класс `BaseConsumer` на `aio_pika`:
  - подключение через `connect_robust`;
  - параметризованные queue_name, prefetch, max_retries;
  - retry с exponential backoff (через DLX/DLQ или per-message header);
  - graceful shutdown по SIGTERM;
  - метрики `mq_messages_consumed_total{queue,result}`.
- Документация в `infrastructure/rabbitmq/README.md`: как написать новый consumer (пример с `match_notifications`).

**Acceptance:**
- Backend `rating_consumer` (T-B5) и bot `notification_consumer` (T-T1) построены на этом базовом классе.
- Сообщение, упавшее с исключением 3 раза, попадает в DLQ `<queue>.dlq`.

**Приоритет:** средний. **Оценка:** 3–4 ч.

---

## T-Q3. Добавить DLQ в definitions.json (раздел 3.3)

**Где:** `infrastructure/rabbitmq/definitions.json`.

**Что сделать:**
- Для каждой из 4 рабочих очередей добавить:
  - dead-letter-exchange (`<exchange>.dlx`);
  - DLQ `<queue>.dlq` (durable, без TTL);
  - bindings.
- Обновить healthcheck (если есть) на проверку DLQ.

**Acceptance:**
- `rabbitmqctl list_queues` показывает 4 рабочие + 4 DLQ очереди.
- При намеренном падении consumer'а сообщение оказывается в DLQ.

**Приоритет:** низкий (но желательно сделать до T-T1/T-B5).

---

## T-Q4. Оптимизация Redis-паттернов под нагрузку (поддержка раздела 3.2)

**Где:** `infrastructure/redis/cache_patterns.py`.

**Что сделать (после первого прогона нагрузочного теста DevOps):**
- Проверить, что `ProfileSessionCache.cache_profiles` использует pipeline корректно (сейчас `await pipe.delete/rpush/expire` в asyncio — убедиться, что это не блокировка).
- Добавить метрику `cache_hit_ratio` (через `prometheus_client`, экспортируется backend'ом — координация с T-B4):
  - на каждый `get_next_profile` инкрементировать `cache_lookups_total{result="hit|miss"}`.
- Проверить под 200 RPS, что `redis-cli info stats` не показывает `evicted_keys > 0` — иначе поднять `maxmemory` или сократить TTL.

**Acceptance:**
- Под нагрузочным тестом hit ratio ≥ 80%.
- `redis-cli --latency` показывает p99 < 5 мс.

**Приоритет:** низкий.

---

## T-Q5. Опциональная связка RabbitMQ ↔ Celery (раздел 3.3, опция (б))

**Решить с PM:** если решено использовать RabbitMQ как Celery-broker (вместо Redis) — это даст «обоснованное применение MQ» без необходимости писать consumer'ы.

**Если выбран этот путь:**
- `backend/celery_app.py`: `broker_url = "amqp://..."`.
- `backend/celery_app.py`: `result_backend = "redis://..."` (оставить Redis для результатов).
- Обновить `docker-compose.yml`: добавить `RABBITMQ_URL` в `celery_worker` и `celery_beat`.
- Документировать выбор в stage4_report.

**Это альтернатива** для T-Q2 + T-T1 + T-B5 (consumer'ы). Рекомендую делать **в дополнение** к consumer'ам, потому что:
- Доставка push-уведомлений всё равно требует отдельной очереди.
- Целевая оценка предполагает «обоснованное применение» MQ, а очередь под Celery — это полпути.

**Приоритет:** низкий (опционально).

---

## T-Q6. Раздел в stage4_report (раздел 3.6)

После создания DevOps скелета `docs/stages/stage4_report.md`, заполнить разделы:
- «RabbitMQ» — топология (exchanges/queues/DLQ), consumer'ы и кто что слушает.
- «Redis» — паттерны (ProfileSessionCache, RatingCache, SwipeCounterCache), TTL, hit ratio под нагрузкой.
- «MinIO» — buckets, presigned URL, soft-delete.

**Приоритет:** низкий.

---

## Что НЕ входит в зону Queue/Cache Engineer

- Бизнес-логика consumer'ов (что делать с сообщением) → Backend / Bot.
- `prometheus_client` интеграция в backend-роутах → Backend.
- Запуск consumer'ов как docker-сервисов → DevOps.
- `notification_consumer` в боте → Telegram Bot Developer.

## Definition of Done для Queue/Cache

- [ ] T-Q1: `EventPublisher` — singleton, declare один раз на старт.
- [ ] T-Q2: `BaseConsumer` с retry/DLQ/graceful shutdown готов.
- [ ] T-Q3: DLQ-очереди объявлены в `definitions.json`.
- [ ] T-Q4: Redis-паттерны выдерживают целевую нагрузку, hit ratio ≥ 80%.
- [ ] T-Q5: (опционально) RabbitMQ как Celery-broker.
- [ ] T-Q6: соответствующие разделы в `stage4_report.md`.
