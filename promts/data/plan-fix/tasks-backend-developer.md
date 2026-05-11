# Задачи для Backend Developer

**Промт агента:** `promts/backend_developer.md`
**Источник несоответствий:** `promts/data/plan-fix/plan-fix.md`
**Ветка:** `stage4`

## Контекст

Backend технологически богат (FastAPI + Celery + Redis + RabbitMQ-publisher + MinIO), но:
- Тяжёлые операции делаются синхронно в HTTP-горутине.
- `MinIOClient` создаётся на каждый запрос (нет singleton-а).
- В Prometheus нет бизнес-метрик (только `http_requests_total`).
- Celery используется только для ночного `recalculate_all_ratings`, `.delay()` не вызывается нигде в API.

Твоя задача — вынести «горячие» операции в Celery, добавить бизнес-метрики, сделать MinIO/инфра-клиенты singleton-ами и причесать логирование.

---

## T-B1. Singleton MinIOClient (раздел 3.8)

**Где:** `backend/main.py:71-83`, `backend/services/photo_service.py:99`.

**Что сделать:**
- Создать `MinIOClient` один раз в `lifespan` startup, положить в `app.state.minio_client`.
- В `PhotoService.get_storage_client()` брать из `app.state` через DI (`Request` или dependency).
- Удалить пересоздание клиента на каждый запрос.

**Acceptance:**
- `grep -n "MinIOClient(" backend/` показывает не более 1 места инстанцирования.
- Health-check проходит, загрузка фото работает.
- Под нагрузочным тестом (см. задачи DevOps) p95 загрузки фото не растёт с числом одновременных запросов.

**Приоритет:** средний. **Оценка:** ~1–2 ч.

---

## T-B2. Перевести swipe-публикацию на singleton EventPublisher (раздел 3.8)

**Где:** `backend/api/v1/matching.py:189`.

**Что сделать (согласовать с Queue/Cache, см. T-Q1):**
- После того как `EventPublisher` станет singleton'ом, в `_publish_swipe_events` и `_publish_match_event` использовать общий экземпляр (через `app.state.event_publisher` или DI), без `async with EventPublisher(...)` на каждый свайп.
- Падение RabbitMQ не должно ронять HTTP 200 свайпа — обернуть публикацию в try/except с логом и метрикой `mq_publish_failed_total`.

**Acceptance:**
- Свайп выполняет 0 declare-операций (проверять через RabbitMQ management UI: счётчик `channel.declare` не растёт).
- `nc -z rabbitmq 5672` отключённое — swipe всё равно завершается 200, в логе `WARNING rabbitmq publish failed user=X target=Y`.

**Приоритет:** средний.

---

## T-B3. Расширить Celery до 3 задач (раздел 3.4)

**Файл:** `backend/celery_app.py` + новые модули `backend/tasks/`.

Добавить tasks и вызвать через `.delay()` в HTTP-эндпойнтах:

| Task | Триггер | Аргументы | Что делает |
|------|---------|-----------|-----------|
| `recalculate_user_rating(user_id)` | После каждого свайпа в `matching.py` | `user_id: int` | Пересчёт behavioral-рейтинга только для одного пользователя (точечно, без полного прохода) |
| `process_uploaded_photo(photo_id)` | После `POST /api/v1/profile/photo` | `photo_id: int` | Валидация изображения (тип/размер), генерация thumbnail (Pillow) и загрузка превью в MinIO |
| `send_match_notification(user_id, match_id)` | При создании мэтча в `_handle_match` | `user_id, match_id: int` | Публикация в `match_notifications` (RabbitMQ); подбирает текст и шлёт в очередь, бот ловит и доставляет (см. T-T1) |

**Acceptance:**
- `grep -rn "\.delay(" backend/` находит минимум 3 вызова в API-коде.
- Celery worker логирует обработку tasks.
- `recalculate_all_ratings` остаётся в beat-расписании, но больше не является единственным потребителем Celery.

**Приоритет:** средний. **Оценка:** 4–6 ч.

---

## T-B4. Бизнес-метрики Prometheus (раздел 3.5)

**Где:** `backend/main.py`, `backend/api/v1/matching.py`, `backend/services/*.py`.

**Что добавить (через `prometheus_client`):**
```python
from prometheus_client import Counter, Histogram

swipes_total = Counter("swipes_total", "Свайпы", ["action"])  # like, skip
matches_total = Counter("matches_total", "Новые мэтчи")
matching_session_duration = Histogram("matching_session_duration_seconds", "Длительность подбора 10 анкет")
rating_recalc_duration = Histogram("rating_recalc_duration_seconds", "Время точечного пересчёта рейтинга", ["scope"])  # user|all
cache_hit_ratio = Counter("cache_lookups_total", "Кэш ProfileSessionCache", ["result"])  # hit|miss
mq_publish_failed_total = Counter("mq_publish_failed_total", "RabbitMQ publish failures", ["exchange"])
```

Инкрементировать в соответствующих местах: `matching.swipe_profile`, `_handle_match`, `ProfileSessionCache.get_next_profile`, `RatingCalculator.recalculate_*`, обработчики ошибок MQ.

**Acceptance:**
- `curl http://backend:8005/metrics | grep swipes_total` показывает счётчик.
- В Grafana (после задачи DevOps T-D3) появляются панели.

**Приоритет:** средний.

---

## T-B5. RabbitMQ rating consumer (раздел 3.3, опция (а))

**Файл:** `backend/workers/rating_consumer.py` (новый).

**Что сделать:**
- Подписаться на очередь `swipe_processing` (routing key `swipe.*`) через `aio_pika`.
- На каждое событие свайпа триггерить `recalculate_user_rating.delay(swipe_event.from_user_id)`.
- Запускать как отдельный процесс (отдельный entry-point в Docker, см. задачу DevOps).
- Использовать prefetch=50, ack после успешного `.delay()`.

**Acceptance:**
- При публикации 1000 свайпов в RabbitMQ очередь `swipe_processing` опустошается, в Celery видны 1000 задач `recalculate_user_rating`.
- При падении worker'а сообщения не теряются (durable + ack-after-process).

**Приоритет:** средний.

---

## T-B6. Контекстное логирование (раздел 3.10)

**Где:** все `logger.warning(...)`, `logger.error(...)` в `backend/api/`, `backend/services/`.

**Что сделать:**
- Везде, где ловится исключение в обработке свайпа/мэтча/фото/рейтинга, в сообщение лога добавить:
  - `user_id`, `target_id` (для свайпов);
  - `match_id` (для мэтчей);
  - `photo_id` (для фото);
  - `type(e).__name__` и `str(e)`.
- Пройтись по `"⚠️ Redis недоступен"` и аналогичным generic-сообщениям, заменить на формат `Ошибка в модуле <module>: <context>` как в требованиях.

**Acceptance:**
- `grep -rn "logger\.\(warning\|error\)" backend/ | grep -v "user_id\|match_id\|photo_id"` возвращает 0 строк в местах с доступным контекстом.

**Приоритет:** низкий.

---

## T-B7. Раздел в stage4_report (раздел 3.6)

Когда DevOps создаст скелет `docs/stages/stage4_report.md`, заполнить разделы:
- «Backend / Celery» — список tasks, частоты вызова, метрики.
- «Backend / Метрики» — список Prometheus-метрик с описанием.
- «Backend / RabbitMQ consumers» — `rating_consumer`.

**Приоритет:** низкий.

---

## Что НЕ входит в зону Backend Developer

- Создание GitHub Actions workflow → DevOps.
- Написание `.jmx` плана → DevOps.
- `notification_consumer` в боте → Telegram Bot Developer.
- Рефакторинг `EventPublisher` (singleton + setup_topology) → Queue/Cache Engineer (Backend только пользуется готовым клиентом).
- Изменения в `docker-compose.yml`, кроме согласованных параметров (PORT, env names) → DevOps.

## Definition of Done для Backend

- [ ] T-B1: `MinIOClient` — singleton.
- [ ] T-B2: `EventPublisher` используется как singleton, fail-safe для публикации.
- [ ] T-B3: 3 новые Celery-tasks, `.delay()` вызывается в HTTP-пути.
- [ ] T-B4: 6 бизнес-метрик в `/metrics`.
- [ ] T-B5: `rating_consumer` слушает `swipe_processing` и дергает Celery.
- [ ] T-B6: бизнес-логи имеют контекст (user_id/match_id/photo_id).
- [ ] T-B7: разделы backend в `stage4_report.md` заполнены.
