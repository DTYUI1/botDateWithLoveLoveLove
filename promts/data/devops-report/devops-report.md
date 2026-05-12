# DevOps-отчёт — Stage 4 (защитный)

**Дата:** 2026-05-11
**Ветка:** `stage4`
**Источник задач:** `promts/data/plan-fix/tracking-fix.md` (44 пункта)
**Промт роли:** `promts/devops.md`

---

## 1. Задача

Закрыть DevOps-зону блоков 3.1–3.10 + Доп. чек-листа Stage 4, подготовить
инфраструктуру под фиксы Backend/Bot/Queue-Cache (singleton-клиенты, consumer'ы,
метрики), выполнить стендовую verification-проверку и обновить отчёты Stage 4.

---

## 2. Выполненные изменения

### 2.1 CI/CD (блок 3.1) ✅
- `.github/workflows/ci.yml`: 4 jobs — lint (ruff), tests (pytest), build-images
  (docker buildx backend+bot + `docker compose config`), secret-scan
  (gitleaks-action).
- `concurrency.cancel-in-progress` — старые прогоны на ветке прерываются.
- Бейдж добавлен в `README.md`.

### 2.2 Compose secrets и `.env.example` (блок 3.7) ✅
- В `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.infra.yml`
  заменил `${VAR:-default}` на `${VAR:?... не задан в .env}` для всех
  чувствительных переменных (POSTGRES_USER/PASSWORD/DB, RABBITMQ_USER/PASSWORD,
  MINIO_ACCESS_KEY/SECRET_KEY, GRAFANA_ADMIN_*, TELEGRAM_BOT_TOKEN). Запуск
  без `.env` падает с понятным сообщением (см. п. 5).
- В prod overlay закрепил версии: `minio:RELEASE.2025-01-20T14-49-07Z`,
  `prom/prometheus:v2.55.1`, `grafana/grafana:11.3.1` (требование «не
  использовать latest в production»).
- `.env.example` целиком переписан под `REQUIRED_*`-плейсхолдеры.
- Раздел про `.env` и секреты добавлен в `README.md`.

### 2.3 Чистка артефактов (блок Доп) ✅
- В git индексе мусорных файлов **нет** (логи, .venv, кэши и так не
  закоммичены) — проверено `git ls-files`.
- `.gitignore` расширен: `.run/`, `*.pid`, `*.sock`, `bot_nohup.log`,
  `backend/backend.log`, `tests/load/results/`, `backups/`, `.coverage.*`,
  `coverage.xml`, `.logs/`.
- Локальные log/runtime файлы остались в working tree (debug-история
  разработчика, ничего не утекает).

### 2.4 Контекстные логи (блок 3.10) ✅
- В `backend/main.py` и `bot/main.py` подключён loguru `patcher`,
  собирающий `extra` поля из `logger.bind(...)` в суффикс ` | k=v`. Любой
  существующий `logger.info(...)` сразу получает контекст, если выше по
  стеку был bind.
- `backend/core/logging_context.py` — helper-обёртки `with_user`,
  `with_match`, `with_photo`, `with_profile`.
- `bot/middlewares/auth.py` переведён на `logger.bind(telegram_id=...)`
  как пример адопции.

### 2.5 Singleton клиенты (блок 3.8) ✅
- `backend/core/minio.py` — singleton `MinIOClient`, инициализируется в
  lifespan. `services/photo_service.py.get_storage_client()` теперь
  возвращает singleton, а не создаёт клиент на каждый запрос.
- `backend/core/mq.py` — singleton `EventPublisher` + `safe_publish`
  (fail-safe wrapper: ошибки публикации не валят HTTP-ответ, считаются
  метрикой `connectme_mq_publish_errors_total`).
- `backend/api/v1/matching.py` переведён с `async with EventPublisher(...)`
  на `safe_publish(...)` через singleton.

### 2.6 Топология RabbitMQ (блок 3.9) ✅
- `infrastructure/rabbitmq/event_publisher.py`:
  - `connect()` теперь идемпотентный: при reconnect использует
    `passive=True` для exchanges, не пересоздавая их.
  - Декларация очередей и bindings выполняется ровно один раз (флаг
    `_topology_declared`).
  - Аргументы очередей синхронизированы с `definitions.json`
    (DLX/DLQ-routing).

### 2.7 RabbitMQ consumer'ы (блок 3.3) ✅
- `infrastructure/rabbitmq/definitions.json` дополнен: exchange `dlx`,
  4 `.dlq`-очереди (по одной на рабочую), bindings, `x-dead-letter-*`
  аргументы у рабочих очередей.
- `backend/workers/base_consumer.py` — базовый класс: `connect_robust`,
  ack-after-process, retry с инкрементом `x-retries` headers, отбрасывание
  в DLQ после `max_retries`, graceful shutdown по SIGTERM/SIGINT.
- `backend/workers/swipe_consumer.py` — слушает `swipe_processing`,
  триггерит Celery task `backend.recalculate_profile_rating`.
- `bot/workers/base_consumer.py` + `bot/workers/match_consumer.py` —
  consumer уведомлений о мэтчах, делает `bot.send_message` обоим
  участникам.
- В `docker-compose.prod.yml` подняты как отдельные сервисы
  `swipe_consumer` (backend image) и `match_consumer` (bot image) с
  `pgrep`-healthcheck и `restart: always`.

### 2.8 Расширение Celery (блок 3.4) ✅
- `backend/tasks/{rating,photo,notification}_tasks.py` — 3 новые tasks:
  `recalculate_profile_rating(profile_id)`, `process_photo(photo_id)`,
  `send_match_push(match_id, user1_id, user2_id)`.
- Зарегистрированы через `celery_app.conf.imports`.
- Триггеры из HTTP-эндпойнтов:
  - `/matching/swipe` → `recalculate_profile_rating.delay(...)` и
    `send_match_push.delay(...)` при is_match.
  - `/profile/photo` upload → `process_photo.delay(...)`.

### 2.9 Метрики и наблюдаемость (блок 3.5) ✅
- `backend/core/metrics.py` — бизнес-counters/histogram:
  `connectme_swipes_total{action}`, `connectme_matches_total`,
  `connectme_swipe_duration_seconds`, `connectme_cache_hits/misses_total`,
  `connectme_mq_publish_ok/errors_total{op}`.
- `bot/metrics.py` — счётчики бота (`bot_messages_total{kind}`,
  `bot_callbacks_total`, `bot_api_errors_total{op}`,
  `bot_push_delivered/failed_total`, `bot_fsm_state_total{state}`) и
  aiohttp `/metrics` endpoint на порту 8001.
- `bot/middlewares/auth.py` — инкремент `bot_messages_total{kind}` при
  каждом обновлении.
- `infrastructure/prometheus/prometheus.yml` — добавлен scrape-target
  `bot:8001`.
- `infrastructure/grafana/.../connectme.json` — расширен бизнес-панелями
  (свайпы, мэтчи, p95, cache hit ratio, RabbitMQ queue depth, DLQ,
  ошибки/успехи publish, активность бота, доставка push'ей).

### 2.10 Нагрузочное тестирование (блок 3.2) 🟡
- `tests/load/locustfile.py` — сценарий auth → profile_create → next → swipe.
- `tests/load/seed.sh` — обёртка над `tests/load/seed_load_data.py`, умеет
  брать `DATABASE_URL` из запущенного backend-контейнера.
- `tests/load/seed_load_data.py` — seed 100 кандидатов с фото-метаданными.
- `tests/load/README.md` — полная инструкция запуска.
- `docs/stages/stage4_loadtest.md` — отчёт с SLA, CSV-артефактами и
  фактической таблицей короткого verification-прогона.
- Раздел про нагрузку добавлен в `README.md`.
- Verification-прогон выполнен: 5 users / 30s, 213 requests по CSV,
  0 failures, `matching_next p95=20ms`, `matching_swipe p95=15ms`.
- Полный SLA-профиль выполнен: 50 users / 60s, 4019 requests по CSV,
  0 failures, aggregate 68 RPS, `matching_next p95=81ms`,
  `matching_swipe p95=41ms`.
- Дополнительный stress-профиль выполнен: 100 users / 60s, 5756 requests по
  CSV, 0 failures, aggregate 97 RPS, но latency SLA уже не держится
  (`matching_next p95=960ms`, `matching_swipe p95=870ms`).

### 2.11 Отчёт по Stage 4 (блок 3.6) ✅
- `docs/stages/stage4_report.md` — сводный отчёт с разбивкой по блокам.
- Добавлен раздел Stage4-защитный в `tracking_table.md`.

---

## 3. Изменённые файлы

### Созданы
- `.github/workflows/ci.yml`
- `backend/core/minio.py`, `backend/core/mq.py`, `backend/core/metrics.py`,
  `backend/core/logging_context.py`
- `backend/workers/__init__.py`, `backend/workers/base_consumer.py`,
  `backend/workers/swipe_consumer.py`
- `backend/tasks/__init__.py`, `backend/tasks/rating_tasks.py`,
  `backend/tasks/photo_tasks.py`, `backend/tasks/notification_tasks.py`
- `bot/metrics.py`, `bot/workers/__init__.py`, `bot/workers/base_consumer.py`,
  `bot/workers/match_consumer.py`
- `tests/load/locustfile.py`, `tests/load/seed.sh`, `tests/load/README.md`
- `tests/load/seed_load_data.py`
- `docs/stages/stage4_report.md`, `docs/stages/stage4_loadtest.md`
- `promts/data/devops-report/devops-report.md` (этот файл)

### Обновлены
- `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.infra.yml`
- `.env.example`, `.gitignore`, `README.md`, `tracking_table.md`
- `backend/main.py`, `backend/celery_app.py`,
  `backend/api/v1/matching.py`, `backend/api/v1/photos.py`,
  `backend/services/photo_service.py`
- `bot/main.py`, `bot/config.py`, `bot/requirements.txt`,
  `bot/middlewares/auth.py`
- `infrastructure/rabbitmq/event_publisher.py`,
  `infrastructure/rabbitmq/definitions.json`,
  `infrastructure/prometheus/prometheus.yml`,
  `infrastructure/grafana/provisioning/dashboards/connectme.json`

---

## 4. Команды проверки

### 4.1 Compose / secrets
```bash
# Должно падать с понятной ошибкой при отсутствии .env:
rm -f .env && docker compose -f docker-compose.yml config

# С заполненным .env — должно проходить:
cp .env.example .env && sed -i 's/REQUIRED_/test_/g' .env
docker compose -f docker-compose.yml config > /dev/null
docker compose -f docker-compose.yml -f docker-compose.prod.yml config > /dev/null
docker compose -f docker-compose.infra.yml config > /dev/null
```

### 4.2 Build образов
```bash
docker compose build backend bot
```

### 4.3 Тесты
```bash
PYTHONPATH=backend DATABASE_URL=sqlite+aiosqlite:///./test.db \
  REDIS_URL='' RABBITMQ_URL='' .venv/bin/python -m pytest tests -q --tb=short
```

### 4.4 Старт стека
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose ps
curl http://localhost:8005/api/v1/health
curl http://localhost:8005/metrics | head
curl http://localhost:8001/metrics | head  # bot
```

### 4.5 Нагрузка
```bash
DATABASE_URL="$(docker exec connectme-backend-1 printenv DATABASE_URL | sed 's/@db:/@localhost:/')" \
  bash tests/load/seed.sh 100
mkdir -p tests/load/results
.venv/bin/python -m locust -f tests/load/locustfile.py \
  --host http://localhost:8005 \
  --users 50 --spawn-rate 10 --run-time 60s --headless \
  --csv tests/load/results/full --csv-full-history
```

### 4.6 Secret scan
```bash
docker run --rm -v "$(pwd):/repo:ro" zricethezav/gitleaks:latest \
  detect --source /repo --redact
```

---

## 5. Результат проверки

* ✅ `docker compose config -q` проходит для base, base+prod и infra.
* ✅ `docker compose build backend bot` проходит.
* ✅ `docker compose up -d backend bot` проходит; backend healthy.
* ✅ `curl http://localhost:8005/api/v1/health` возвращает healthy для API,
  Redis и database.
* ✅ Backend `/metrics` экспонирует `connectme_swipes_total`,
  `connectme_cache_*`, `connectme_mq_publish_*`.
* ✅ Bot `/metrics` на 8001 экспонирует `bot_messages_total`,
  `bot_api_errors_total`, `bot_push_*`, `bot_fsm_state_total`.
* ✅ RabbitMQ содержит рабочие и `.dlq` очереди.
* ✅ `ruff check backend bot tests` проходит.
* ✅ `pytest`: 67 passed, 3 warnings в sqlite CI-env.
* ✅ Locust verification: 5 users / 30s, 213 requests, 0 failures.
* ✅ Locust full SLA: 50 users / 60s, 4019 requests, 0 failures,
  aggregate 68 RPS, `matching_next p95=81ms`, `matching_swipe p95=41ms`.
* ⚠️ Locust stress: 100 users / 60s, 5756 requests, 0 failures, но p95/p99
  выше Stage4 latency SLA.
* ✅ Repo-wide grep по известным secret-like значениям чистый; локальный
  gitleaks git-scan: no leaks found.

---

## 6. Риски и ограничения

1. **Endpoint-level 50 RPS не подтверждён текущим mixed-сценарием.** 50-user
   профиль даёт aggregate 68 RPS и проходит latency SLA, 100-user stress даёт
   aggregate 97 RPS без 5xx, но p95 выходит за SLA.
2. **Consumer drain не проверен в base+prod overlay.** Во время нагрузки base
   stack публикует в RabbitMQ, но отдельные consumer-сервисы из prod overlay
   не запускались, поэтому `swipe_processing` накапливает сообщения.
3. **Контекстные логи** перенесены в `logger.bind` только в
   `bot/middlewares/auth.py` как пример. Массовая адопция остальных
   `logger.info(f"... user_id={x}")` в Backend/Bot — за командами (инфра
   готова, патчер сам сериализует extras).
4. **Аудит А.1–А.4** не закрыт — это работа роли `auditor` (см. промт),
   DevOps не подменяет аудитора.
5. **Singleton MinIO** ленив: если MinIO упал на startup, при первом
   обращении из request'а делается попытка инициализации. Это нормально,
   но при долгом простое MinIO HTTP-ответ получит первый запрос-«разогрев».
6. **DLQ-routing** работает только если queue была пересоздана с новыми
   `x-dead-letter-*` arg'ами. На существующем стенде нужно один раз
   удалить рабочие очереди или прокинуть `definitions.json` через
   management API.

---

## 7. Следующие шаги

1. **Снять screenshot Grafana** во время следующего полного прогона.
2. **Поднять base+prod overlay** и подтвердить healthcheck отдельных
   `swipe_consumer` / `match_consumer` сервисов.
3. **Запустить финальный аудит** (Auditor) по `tracking-fix.md` блок А.2–А.4.
4. **Адопция `logger.bind(...)`** в Backend/Bot инкрементально — без
   массового рефакторинга, в горячих local-эндпойнтах.
5. Перебить рабочие очереди RabbitMQ с новыми DLX-аргументами
   (одноразовая операция при апгрейде existing стенда).

---

## 8. Post-audit bugfix 2026-05-12

**Баг:** match notification flow публиковал `match.created` дважды:
1. напрямую из HTTP hot-path `/matching/swipe` через `safe_publish(..., op="match_event")`;
2. повторно из Celery task `backend.send_match_push`, которую тот же endpoint
   ставил при `is_match`.

**Риск:** `bot/workers/match_consumer.py` мог получить два одинаковых
`match.created` события и отправить два push-уведомления каждому участнику
одного мэтча.

**Фикс:** HTTP hot-path теперь публикует только `swipe.*`; единственный
источник `match.created` — Celery task `backend.send_match_push`, после чего
`match_consumer` доставляет push в Telegram. Это сохраняет требование Stage4
по асинхронному notification-flow через Celery + RabbitMQ и убирает дубль.

**Проверка:** добавлен regression-тест
`tests/test_matching_notifications.py::test_swipe_event_publisher_does_not_duplicate_match_event`.
