# Доп. этап продукта: сервис нотификаций (match → push)

**Статус:** реализован и доставляется до Telegram.
**Дата фиксации:** 2026-05-12
**Соответствие `req.md`:** п.21 «Другой этап, обговариваем лично. Пример:
сервис notification и т. д.» (0–3 балла за новый пункт).

---

## 1. Цель

Доставлять обоим участникам мэтча push-уведомление в Telegram **вне
HTTP-цикла swipe**: HTTP-эндпойнт `/api/v1/matching/swipe` отдаёт 200
сразу, как только записал свайп в БД и опубликовал событие в RabbitMQ;
любые задержки Telegram API / временная недоступность бота не влияют на
ответ API и не блокируют UX свайпера.

Без отдельного notification-сервиса единственный путь — синхронно дёргать
Telegram API из обработчика swipe, что:
- удлиняет p95 ответа `/swipe` на стоимость round-trip к Telegram;
- ломает HTTP при любом сбое в Telegram;
- не масштабируется (один HTTP worker = один поток к Telegram).

С отдельным сервисом swipe-handler делает только `safe_publish`
(fail-safe), а вся работа с Telegram уходит на отдельный consumer
с независимым жизненным циклом.

---

## 2. Сценарий

```
Пользователь делает свайп
  └─ POST /api/v1/matching/swipe
      ├─ запись в БД (Postgres)
      ├─ если случился match:
      │    ├─ Celery: backend.send_match_push.delay(match_id, u1, u2)
      │    │   └─ publisher.publish_match_event(...) →
      │    │       RabbitMQ exchange `match_events`
      │    │           → queue `match_notifications`
      │    └─ HTTP 200 OK (UX не блокируется)
      └─ swipe_event публикуется в очередь `swipe_events` для рейтинга

Bot side (отдельный сервис):
  bot/workers/match_consumer.py:
    └─ слушает `match_notifications`
        ├─ для каждого user_id ищет telegram_id через
        │   GET /api/v1/profile/{profile_id}/telegram_id (backend API)
        ├─ await bot.send_message(telegram_id, MATCH_PUSH_TEMPLATE)
        ├─ инкрементит bot_push_delivered_total / bot_push_failed_total
        └─ при ошибке отправки: raise → base_consumer повторяет
           через retry, после лимита уходит в DLQ
```

---

## 3. Архитектура и точки входа

| Слой | Файл | Что делает |
|---|---|---|
| Trigger из API | `backend/api/v1/matching.py` (`swipe` endpoint) | `send_match_push.delay(...)` при match=True |
| Celery task | `backend/tasks/notification_tasks.py` | `_send_match_push` → `publisher.publish_match_event` |
| MQ publisher | `backend/core/mq.py` + `infrastructure/rabbitmq/event_publisher.py` | singleton, `safe_publish`, robust reconnect |
| Топология | `infrastructure/rabbitmq/definitions.json` | exchange `match_events`, queue `match_notifications`, DLQ `match_notifications.dlq` |
| Consumer | `bot/workers/match_consumer.py` | listen queue → Telegram API → метрики |
| Base retry | `bot/workers/base_consumer.py` | ack/nack, exponential retry, DLQ after limit |
| Lookup | `backend/api/v1/profile.py` (`/profile/{id}/telegram_id`) | возвращает telegram_id по profile_id |
| Bot Bot/Session | `bot/workers/match_consumer.py` (`main`) | отдельный `Bot` + `AiohttpSession`, прокси из env |
| Метрики | `bot/metrics.py` | `bot_push_delivered_total`, `bot_push_failed_total` |
| Compose | `docker-compose.prod.yml` (`match_consumer`) | отдельный сервис, healthcheck, restart: always |

---

## 4. Гарантии и точки отказа

| Сценарий | Поведение |
|---|---|
| Бот выключен | Сообщения копятся в `match_notifications`, поднялся — разобрал |
| Telegram API временно 5xx | Consumer ловит исключение, делает `raise` → base_consumer перепубликует с `x-retries+1` |
| Превышен retry-лимит | Сообщение уходит в `match_notifications.dlq` — оператор может разобрать вручную |
| RabbitMQ упал | `safe_publish` в backend не уронит HTTP 200, событие просто потеряется (acceptable trade-off для push, см. п.5) |
| Backend lookup упал | Consumer пишет warning и пропускает конкретного user, остальные доставляются |
| Бот сам упал mid-handle | `aio_pika` не подтвердит ack, RabbitMQ передоставит сообщение |

---

## 5. Трейд-оффы

- **Push — не критичный канал.** Если RabbitMQ недоступен и
  `safe_publish` вернул `False`, мы предпочли «потерять push» вместо
  «уронить HTTP 200» свайперу. Альтернатива — outbox-таблица в Postgres,
  но это уже за рамками доп. этапа.
- **Не персонализируем текст.** Сейчас один шаблон
  `MATCH_PUSH_TEMPLATE`. Имя/аватар собеседника в push не подтягивается,
  пользователь видит детали уже в `/matches`. Это сознательное решение
  — push должен быть быстрым и без лишних запросов.

---

## 6. Метрики

Все доступны на `bot:8001/metrics` и видны в Grafana row «Bot»:

- `bot_push_delivered_total` — успешно доставленные push.
- `bot_push_failed_total` — ошибки доставки до Telegram (Telegram 5xx,
  блок бота пользователем, неверный chat_id).
- `bot_messages_total{kind="message|callback_query"}` — фоновая
  активность, по которой видно, что бот сам жив.

Backend-сторона:

- `connectme_matches_total` — счётчик случившихся мэтчей (входной
  «спрос» на push).
- `connectme_mq_publish_ok_total{op="match_event"}` — успешные публикации.
- `connectme_mq_publish_errors_total{op="match_event"}` — провалы
  `safe_publish`.

Соотношение `matches_total` ↔ `bot_push_delivered_total` показывает
end-to-end доставку.

---

## 7. End-to-end ручной тест

1. Поднять стек: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`.
2. Убедиться, что `match_consumer` healthy:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml ps match_consumer
   ```
3. Создать обоюдный лайк (например, из тестового аккаунта Яр на
   замоканного пользователя 9_000_000_001 → потом обратный лайк через
   backend API, чтобы случился match).
4. Проверить:
   - В логах `bot/workers/match_consumer.py` появилась запись
     `[MatchConsumer] push отправлен match_id=... telegram_id=...`.
   - В Telegram оба участника получили `💖 У вас новый мэтч!`.
   - В Grafana row «Bot» панель «Доставка push'ей» инкрементилась
     (`delivered +1`).
   - В RabbitMQ management UI (`localhost:15672`) очередь
     `match_notifications` опустела, в `.dlq` пусто.

---

## 8. Что зачитывается как доп. этап

По `req.md` п.21 «Другой этап… до 3 баллов за каждый новый пункт».
Сервис подходит под определение «новый этап» по трём признакам:

1. **Самостоятельный жизненный цикл** — отдельный docker-сервис
   `match_consumer` с healthcheck, может перезапускаться независимо
   от бота-handler-а.
2. **Собственная топология MQ** — отдельный exchange/queue/DLQ.
3. **Собственный observability-слой** — отдельные метрики и логи с
   `match_id/user_id` контекстом.

Это не «celery в boilerplate», а полноценный fan-out flow,
аналог Notification Service из микросервисных шаблонов.

---

## 9. Ссылки

- HTTP-эндпойнт swipe: `backend/api/v1/matching.py`
- Celery task: `backend/tasks/notification_tasks.py`
- Consumer: `bot/workers/match_consumer.py`
- Base consumer: `bot/workers/base_consumer.py`
- Топология: `infrastructure/rabbitmq/definitions.json`
- Метрики: `bot/metrics.py`, `backend/core/metrics.py`
- Compose: `docker-compose.prod.yml` (сервис `match_consumer`)
- Stage4 итоги: `docs/stages/stage4_report.md`
