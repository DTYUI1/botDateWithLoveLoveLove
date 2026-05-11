# Задачи для Telegram Bot Developer

**Промт агента:** `promts/telegram_bot_developer.md`
**Источник несоответствий:** `promts/data/plan-fix/plan-fix.md`
**Ветка:** `stage4`

## Контекст

Бот функционально работает (свайпы, мэтчи, чат, FSM на aiogram 3), `@HUScorp_bot` подтверждён в `tracking_table.md`. НО:
- Уведомление о мэтче приходит **синхронно** из ветки `swipe_profile` — это блокирует HTTP-горутину backend'а и не использует существующий exchange `match_events`.
- Бот **не инструментирован** Prometheus'ом — нет ни одной метрики, по которой мы видим, что бот жив и обрабатывает callback'и.

Твоя задача — закрыть последнюю milю между backend и пользователем через RabbitMQ-consumer, и поднять метрики бота.

---

## T-T1. Notification consumer для match_notifications (раздел 3.3)

**Файл:** `bot/workers/notification_consumer.py` (новый).

**Что сделать:**
- Использовать базовый `BaseConsumer` из задачи Queue/Cache T-Q2 (если он готов, иначе временно `aio_pika` напрямую).
- Подписаться на очередь `match_notifications` (routing key `match.created`).
- На сообщение вида `{"user1_id": int, "user2_id": int, "match_id": int}`:
  1. Для каждого `user_id` найти соответствующий `telegram_id` через Backend API (`GET /api/v1/users/{id}/telegram` или эквивалент — согласовать с Backend).
  2. Отправить сообщение через `bot.send_message(telegram_id, ...)` с inline-кнопкой «Написать» (`callback_data="chat:open:{match_id}"`).
  3. Ack после успешной отправки; nack без requeue, если Telegram вернул 403 (пользователь заблокировал бота).
- Запускаться **отдельным процессом** (новый entry point `python -m bot.workers.notification_consumer`).
- В `docker-compose.yml` появится сервис `bot_consumer` (это задача DevOps T-D6).

**Acceptance:**
- В backend убрана синхронная отправка `bot.send_message` из `swipe_profile` (если она там была), теперь её делает consumer.
- При создании мэтча оба пользователя получают сообщение в течение ≤ 2 секунд.
- При временной недоступности Telegram API (например, прокси упал) сообщения копятся в `match_notifications`, не теряются.

**Приоритет:** средний. **Оценка:** 3–4 ч.

---

## T-T2. Bot Prometheus metrics endpoint (раздел 3.5)

**Файл:** `bot/metrics.py` + интеграция в `bot/main.py`.

**Что сделать:**
- Поднять отдельный aiohttp-сервер на порту `9100` (или согласованном с DevOps) с эндпойнтом `/metrics`.
- Метрики:
  ```python
  bot_messages_total = Counter("bot_messages_total", "Сообщения от пользователей", ["command"])
  bot_callbacks_total = Counter("bot_callbacks_total", "Callback-запросы", ["action"])  # swipe.like, swipe.skip, chat.open
  bot_api_errors_total = Counter("bot_api_errors_total", "Ошибки запросов в backend", ["endpoint", "status"])
  bot_notifications_delivered_total = Counter("bot_notifications_delivered_total", "Доставленные пуши о мэтчах", ["result"])  # ok|blocked|error
  bot_fsm_state_total = Gauge("bot_fsm_state_total", "Текущее число пользователей в FSM-состоянии", ["state"])
  ```
- Инкрементировать в middleware (для `bot_messages_total`), в callback-обработчиках (`bot_callbacks_total`), в `APIClient` (для `bot_api_errors_total`), в `notification_consumer` (для `bot_notifications_delivered_total`).

**Acceptance:**
- `curl http://bot:9100/metrics` отдаёт `bot_*` метрики.
- DevOps добавил `bot:9100` в `prometheus.yml` scrape_configs (задача T-D3).
- В Grafana появилась панель «Bot: callbacks/min».

**Приоритет:** средний. **Оценка:** 2–3 ч.

---

## T-T3. Убрать синхронную отправку match-уведомлений (раздел 3.4)

**Где:** искать в `bot/handlers/` и `backend/api/v1/matching.py` место, где после `is_match=True` бот сразу отправляет сообщение второму пользователю.

**Что сделать:**
- Backend публикует событие в `match_events` (это уже работает) → consumer (T-T1) доставляет сообщение.
- Сейчас (по аудиту) уведомление шлётся напрямую из бота при свайпе через HTTP-ответ → оставить **только** доставку инициатору свайпа (он получает «🎉 Мэтч!» в ответе на свой клик), а уведомление второму пользователю должно идти через consumer.

**Acceptance:**
- `grep -rn "bot.send_message" bot/handlers/` показывает только сообщения, привязанные к текущему чату с пользователем.
- Уведомления о мэтче для второго пользователя приходят строго через `notification_consumer`.

**Приоритет:** средний (зависит от T-T1).

---

## T-T4. Контекстное логирование бота (раздел 3.10)

**Где:** `bot/handlers/*.py`, `bot/api_client.py`, `bot/workers/notification_consumer.py`.

**Что сделать:**
- В каждом `logger.error`/`logger.warning` указывать `telegram_id`, `match_id` (если применимо), `callback_data`.
- В `APIClient`: при ошибке HTTP логировать `endpoint`, `status_code`, `telegram_id` (если есть в контексте), `type(e).__name__`.

**Acceptance:**
- При воспроизведении ошибки (отключить backend) в `bot_nohup.log` видно `telegram_id` пользователя, на котором это случилось.

**Приоритет:** низкий.

---

## T-T5. Раздел в stage4_report (раздел 3.6)

После создания DevOps скелета `docs/stages/stage4_report.md`, заполнить:
- «Bot / Notification consumer» — что слушает, сколько обрабатывает, ack-стратегия.
- «Bot / Metrics» — какие метрики выгружаются, на каком порту.

**Приоритет:** низкий.

---

## Что НЕ входит в зону Telegram Bot Developer

- Объявление новых очередей в RabbitMQ → Queue/Cache Engineer.
- Создание метрики `matches_total` на стороне backend → Backend Developer.
- Создание docker-compose сервиса `bot_consumer` → DevOps (бот предоставляет команду запуска, DevOps пакует).
- Изменение endpoint'ов API → Backend Developer (бот только потребляет).

## Definition of Done для Bot

- [ ] T-T1: `notification_consumer.py` слушает `match_notifications`, доставляет push'и.
- [ ] T-T2: `/metrics` доступен, 5 бизнес-метрик бота экспортируются.
- [ ] T-T3: синхронная отправка match-уведомлений второму пользователю удалена.
- [ ] T-T4: бизнес-логи содержат `telegram_id` и контекст.
- [ ] T-T5: разделы бота в `stage4_report.md` заполнены.
