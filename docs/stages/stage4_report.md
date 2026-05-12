# Этап 4: Нагрузка, наблюдаемость, защита — Отчёт

**Дата подготовки:** 2026-05-11
**Статус:** ✅ завершён (Auditor-замечания исправлены, выполнены mixed и
endpoint-focused SLA-прогоны, prod consumer-прогон и финальный аудит)
**Ветка:** `stage4`

---

## 📋 Карта работ

Стейдж 4 = «защитный»: ничего нового в продукте, но всё, что было готово на
этапе 3, должно держать нагрузку, наблюдаться и не валить деплой. Источник
требований — `promts/data/plan-fix/plan-fix.md`, чек-лист —
`promts/data/plan-fix/tracking-fix.md`.

| Блок | Краткое содержание | Статус |
|---|---|---|
| 3.1 CI/CD | GitHub Actions: lint+tests+build+secret-scan, бейдж | ✅ |
| 3.2 Нагрузка | Locust-сценарии, seed, mixed + endpoint-focused SLA CSV, Grafana screenshot | ✅ |
| 3.3 RabbitMQ consumer'ы | base_consumer + DLQ + swipe/match consumer'ы | ✅ |
| 3.4 Celery расширение | rating/photo/notification tasks + триггеры из API | ✅ |
| 3.5 Метрики | backend + bot `/metrics`, scrape, дашборд | ✅ |
| 3.6 Stage4 report | этот документ | ✅ |
| 3.7 Compose secrets | `${VAR:?}`-проверки, чистый `.env.example` | ✅ |
| 3.8 Singleton | MinIO + RMQ publisher один на lifespan | ✅ |
| 3.9 Топология MQ | декларация 1 раз + robust reconnect | ✅ |
| 3.10 Логи | loguru ctx-patcher + helper'ы | 🟡 адопция инкрементальная |
| Доп | `.gitignore` под фактическую структуру | ✅ |
| Аудит А.1–А.4 | финальный аудит и таблица баллов | ✅ |

---

## 🛠 DevOps (Зона ответственности)

### CI/CD (`.github/workflows/ci.yml`)

- 4 jobs: `lint` (ruff), `tests` (pytest), `build-images` (backend+bot
  через buildx), `secret-scan` (gitleaks-action).
- Срабатывание на push в `main` / `develop` / `stage*` и любые PR.
- `concurrency: cancel-in-progress` — последний коммит вытесняет старые
  прогоны на той же ветке.
- Бейдж добавлен в README.

### Compose / секреты (блок 3.7, Доп)

- `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.infra.yml`
  используют `${VAR:?}` для всех чувствительных переменных. Запуск без
  `.env` или с пустым секретом завершается с понятной ошибкой
  (`error while interpolating ... POSTGRES_PASSWORD не задан в .env`).
- `.env.example` содержит только `REQUIRED_*`-плейсхолдеры.
- В prod overlay убран `:latest` у MinIO/Prometheus/Grafana (закреплены
  версии).
- gitleaks-action в CI блокирует случайно закоммиченные секреты.
- `.gitignore` дополнен: `.run/`, `*.pid`, `*.sock`, `bot_nohup.log`,
  `tests/load/results/`, `backups/`, etc.

### Нагрузка (блок 3.2)

- Сценарий: `tests/load/locustfile.py` (auth → profile_create → next → swipe).
- Seed: `tests/load/seed.sh` + `tests/load/seed_load_data.py`, 100 кандидатов
  в `LoadCity` с фото-метаданными.
- Отчёт: `docs/stages/stage4_loadtest.md` с фактической таблицей из CSV.
- Документация запуска: `tests/load/README.md` + раздел в `README.md`.
- Verification-прогон выполнен: 5 users / 30s, 213 requests, 0 failures,
  `matching_next p95=20ms`, `matching_swipe p95=15ms`.
- Полный SLA-профиль выполнен: 50 users / 60s, 4019 requests, 0 failures,
  aggregate 68 RPS, `matching_next p95=81ms`, `matching_swipe p95=41ms`.
- Stress-профиль выполнен: 100 users / 60s, 5756 requests, 0 failures,
  aggregate 97 RPS; p95 latency уже выше SLA, см.
  `docs/stages/stage4_loadtest.md`.
- Endpoint-focused профиль выполнен:
  `matching_next_focused` — 3018 requests, 0 failures, 51.07 RPS, p95=170 ms;
  `matching_swipe_focused` — 3067 requests, 0 failures, 51.87 RPS, p95=81 ms.
- Скриншот Grafana приложен:
  `docs/stages/img/stage4_load_grafana.png`.

### Метрики и наблюдаемость (блок 3.5 DevOps-часть)

- `infrastructure/prometheus/prometheus.yml` — добавлен job
  `connectme-bot` (target `bot:8001`).
- `infrastructure/grafana/provisioning/dashboards/connectme.json` —
  расширен бизнес-панелями: свайпы/мин, мэтчи/мин, p95 swipe duration,
  cache hit ratio, глубина очередей RabbitMQ, отдельная панель для DLQ,
  активность бота, доставка push'ей, ошибки backend-publish.
- Скриншоты Grafana по доменам (live-прогон 20 users / 120s
  от 2026-05-12, подробности — `docs/stages/stage4_loadtest.md`,
  раздел «Grafana panels»):
  - `docs/stages/img/stage4_grafana_rps.png` — Requests per second по
    endpoint'ам.
  - `docs/stages/img/stage4_grafana_p95_latency.png` — p95 latency,
    cold-start пик и установившийся участок.
  - `docs/stages/img/stage4_grafana_5xx_error_rate.png` — 5xx error rate
    (всплеск только на одном photo endpoint во время ручных тестов,
    под Locust 5xx = 0).
  - `docs/stages/img/stage4_grafana_business.png` — свайпы/мин,
    мэтчи/мин, p95 swipe duration, Cache hit ratio (последняя пуста —
    счётчики инкрементируются только при передаче `session_id`,
    Locust такой режим не использует).
  - `docs/stages/img/stage4_grafana_rabbitmq.png` — глубина очередей
    (ready=1 стабильно), DLQ пуста, publish errors = 0, publish ok с
    бизнес-всплеском swipe_event.
  - `docs/stages/img/stage4_grafana_bot.png` — обновления бота,
    callbacks/min, доставка push'ей, ошибки API-клиента.

### Consumer'ы как docker-сервисы (блок 3.3.5)

В `docker-compose.prod.yml`:
- `swipe_consumer` (backend image, команда `python -m workers.swipe_consumer`)
- `match_consumer` (bot image, команда `python -m workers.match_consumer`)
- На каждом `healthcheck` через Python-проверку `/proc` + `restart: always`
  (slim images не содержат `pgrep`).
- В RabbitMQ-сервисе примонтирован `definitions.json` для прелоада
  топологии (включая DLX и `.dlq`-очереди).
- Стендовый запуск подтверждён в `docs/stages/stage4_consumer_run.md`:
  оба consumer-сервиса `healthy`, `swipe_consumer` обрабатывает события
  и триггерит точечный пересчёт рейтинга.

---

## 🧪 Backend

- `backend/core/minio.py` — singleton MinIO-клиент.
- `backend/core/mq.py` — singleton RabbitMQ publisher + `safe_publish`
  (fail-safe).
- `backend/core/metrics.py` — бизнес-метрики Prometheus.
- `backend/tasks/{rating,photo,notification}_tasks.py` — Celery tasks,
  включая Pillow-валидацию и генерацию thumbnail для фото.
- `backend/workers/{base_consumer,swipe_consumer}.py` — consumer для очереди
  свайпов с DLQ/retry/graceful shutdown и инкрементом `x-retries`.
- В `backend/api/v1/matching.py` подключены `safe_publish`, метрики
  свайпов/мэтчей/cache hit/miss и Celery-триггеры
  (`recalculate_profile_rating`, `send_match_push`).
- В `backend/api/v1/photos.py` подключён `process_photo` Celery task.
- В `backend/api/v1/profile.py` добавлен endpoint
  `/api/v1/profile/{profile_id}/telegram_id` для bot match-consumer.

---

## 🤖 Bot

- `bot/main.py` — патчер loguru для `extra → ctx`-суффикса, поднятие
  `/metrics`-сервера на 8001 порту.
- `bot/metrics.py` — счётчики `bot_messages_total`, `bot_callbacks_total`,
  `bot_push_*`, `bot_fsm_state_total` и aiohttp `/metrics` endpoint.
- `bot/api_client.py` инкрементит `bot_api_errors_total{op}` на HTTP/API
  ошибках.
- `bot/middlewares/auth.py` инкрементит `bot_messages_total{kind}`,
  `bot_fsm_state_total{state}` и логирует через `logger.bind(telegram_id=...)`.
- `bot/workers/match_consumer.py` — consumer уведомлений о мэтчах,
  доставка push в Telegram и метрики `bot_push_delivered/failed_total`.
- `bot/config.py` — поля `rabbitmq_url`, `metrics_host`, `metrics_port`.

---

## 🐇 Queue / Cache

- `infrastructure/rabbitmq/definitions.json` — добавлен exchange `dlx` и
  4 `.dlq`-очереди (по одной на рабочую очередь), bindings, аргументы
  `x-dead-letter-*` у рабочих очередей.
- `infrastructure/rabbitmq/event_publisher.py` — `connect()` декларирует
  топологию **один раз** (флаг `_topology_declared`), при reconnect
  использует `passive=True`, чтобы не тратить RTT.
- `backend/workers/base_consumer.py` и `bot/workers/base_consumer.py`
  перепубликуют retry-сообщения с увеличенным `x-retries`; после лимита
  сообщение уходит в DLQ.
- `backend/core/mq.py` — обёртка над publisher с lifecycle hooks и
  `safe_publish`.

---

## 🔗 Ссылки

- Чек-лист: `promts/data/plan-fix/tracking-fix.md`
- Отчёт по нагрузке: `docs/stages/stage4_loadtest.md`
- DevOps-отчёт: `promts/data/devops-report/devops-report.md`
- CI workflow: `.github/workflows/ci.yml`
- Дашборд: `infrastructure/grafana/provisioning/dashboards/connectme.json`
- Финальный аудит: `promts/data/plan-fix/audit-final.md`
- Доп. этап продукта (notification service): `docs/stages/stage_notification_service.md`
