# Чек-лист доработок ConnectMe (этап 4 -> защита)

**Дата:** 2026-05-11  **Ветка:** `stage4`  **Источник:** `promts/data/plan-fix/plan-fix.md`

---

## Аудит DevOps-фиксов от 2026-05-11

Проверено по `promts/auditor.md`: требования `promts/requirements/req.md`,
план `promts/data/plan-fix/plan-fix.md`, отчёт DevOps
`promts/data/devops-report/devops-report.md`, фактические файлы и локальные
команды проверки.

### Что проверено командами

- `docker compose -f docker-compose.yml config -q` — проходит с текущим `.env`.
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config -q` — проходит с текущим `.env`.
- `docker compose -f docker-compose.infra.yml config -q` — проходит с текущим `.env`.
- `git ls-files | rg '(\\.venv|\\.log$|__pycache__|\\.pyc$)'` — tracked-мусора нет.
- `python -m py_compile ...` и `python -m compileall -q backend bot` — синтаксис проходит.
- `.venv/bin/python -m ruff check backend bot tests` — проходит.
- `PYTHONPATH=backend DATABASE_URL=sqlite+aiosqlite:///./test.db REDIS_URL='' RABBITMQ_URL='' .venv/bin/python -m pytest tests -q --tb=short` — **67 passed, 3 warnings**.
- `docker compose build backend bot` — проходит.
- `docker compose up -d backend bot` — проходит, backend healthy.
- `curl http://localhost:8005/api/v1/health` — API/Redis/database healthy.
- `curl http://localhost:8005/metrics` — backend business metrics экспонируются.
- `docker exec connectme-bot-1 ... http://localhost:8001/metrics` — bot metrics экспонируются.
- `bash tests/load/seed.sh 100` — проходит, seed log заполнен.
- `.venv/bin/python -m locust ... --users 5 --run-time 30s` — 213 requests, 0 failures по CSV.
- `.venv/bin/python -m locust ... --users 50 --run-time 60s` — 4019 requests, 0 failures, aggregate 68 RPS по CSV.
- `.venv/bin/python -m locust ... --users 100 --run-time 60s` — 5756 requests, 0 failures, aggregate 97 RPS, но p95 выше SLA.
- `LOCUST_ENDPOINT=next ... locustfile_endpoint.py ...` — 3018 requests, 0 failures, 51.07 RPS, p95=170 ms.
- `LOCUST_ENDPOINT=swipe ... locustfile_endpoint.py ...` — 3067 requests, 0 failures, 51.87 RPS, p95=81 ms.
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps ...` — backend/RabbitMQ/Grafana/Prometheus и оба consumer'а healthy/up.
- Headless Chromium screenshot Grafana — `docs/stages/img/stage4_load_grafana.png`.
- `docker run --rm -v "$(pwd):/repo:ro" zricethezav/gitleaks:latest detect --source /repo --redact` — no leaks found.
- `git diff --check` — проходит.

### Главные выводы

- Быстрые CI-блокеры исправлены: `ruff` и `pytest` зелёные в локальном CI-env.
- Нагрузочный отчёт больше не содержит `TBD`: выполнены verification-run,
  full mixed run, stress-run и endpoint-focused SLA run; CSV-артефакты
  сохранены в `tests/load/results/`.
- Endpoint-level 50 RPS подтверждён отдельным профилем:
  `/matching/next` — 51.07 RPS, p95=170 ms; `/matching/swipe` — 51.87 RPS,
  p95=81 ms; failures=0.
- Исправлены функциональные замечания аудитора: consumer retry инкрементит
  `x-retries`, добавлен endpoint `/api/v1/profile/{id}/telegram_id`,
  `process_photo` выполняет Pillow-валидацию и thumbnail, backend/bot метрики
  реально инкрементируются.
- Repo-wide secret hygiene подтверждён gitleaks git-scan: leaks не найдено.
- Prod consumer healthcheck/drain подтверждён стендово; screenshot Grafana
  приложен; финальный аудит создан.

---

## Блок 3.1 — CI/CD (приоритет: высокий)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| 3.1.1 | Настроить пайплайн lint+tests на push/PR | DevOps | ✅ | `.github/workflows/ci.yml`; локально подтверждено: `ruff` проходит, `pytest` 67 passed |
| 3.1.2 | Добавить шаг сборки docker-образов | DevOps | ✅ | `build-images` в `.github/workflows/ci.yml` |
| 3.1.3 | Добавить шаг security-scan (поиск секретов) | DevOps | ✅ | `gitleaks-action` добавлен; локальный `gitleaks detect --source /repo --redact` — no leaks found |
| 3.1.4 | Бейдж CI в README | DevOps | ✅ | `README.md` |

**Приёмка:** закрыта локальной проверкой; финальный статус GitHub Actions подтвердится после push/PR.

---

## Блок 3.2 — Нагрузочное тестирование (приоритет: высокий)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| 3.2.1 | Согласовать с PM формат теста (JMeter / альтернатива) | DevOps + PM | 🟡 | Выбран Locust, но явного подтверждения PM в репозитории нет |
| 3.2.2 | Подготовить данные (засидить БД) | DevOps | ✅ | `tests/load/seed.sh`, `tests/load/seed_load_data.py`, `tests/load/results/seed.log` |
| 3.2.3 | План-сценарии для критичных endpoints (auth / matching/next / swipe) | DevOps | ✅ | `tests/load/locustfile.py` |
| 3.2.4 | Прогон + сохранение результатов | DevOps | ✅ | Выполнены verification, mixed full/stress и endpoint-focused runs; CSV в `tests/load/results/*_stats.csv` |
| 3.2.5 | Отчёт с графиками, p95, узкими местами | DevOps | ✅ | `docs/stages/stage4_loadtest.md`, `docs/stages/img/stage4_load_grafana.png`; p95/p99 из CSV, включая bottleneck `TooManyConnectionsError` при aggressive setup |
| 3.2.6 | Инструкция запуска в README | DevOps | ✅ | `README.md`, `tests/load/README.md` |

**Приёмка:** закрыта по DevOps-части. Verification/full/stress CSV есть,
endpoint-focused RPS-профиль подтверждает 50+ RPS на обоих matching endpoints;
Locust как замена JMeter остаётся PM-зависимым пунктом.

---

## Блок 3.3 — RabbitMQ consumer'ы (приоритет: средний)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| 3.3.1 | Базовый механизм consumer'ов (retry, DLQ, graceful shutdown) | Queue/Cache | ✅ | `backend/workers/base_consumer.py`, `bot/workers/base_consumer.py`; retry перепубликует сообщение с `x-retries + 1`, после лимита DLQ |
| 3.3.2 | DLQ для рабочих очередей | Queue/Cache | ✅ | `infrastructure/rabbitmq/definitions.json` |
| 3.3.3 | Consumer уведомлений о мэтчах в боте | Bot | ✅ | `bot/workers/match_consumer.py`, `backend/api/v1/profile.py`; endpoint `/api/v1/profile/{id}/telegram_id` добавлен, push metrics подключены |
| 3.3.4 | Consumer событий свайпов в backend (триггер пересчёта рейтинга) | Backend | ✅ | `backend/workers/swipe_consumer.py` |
| 3.3.5 | Запуск consumer'ов как отдельных docker-сервисов + healthcheck | DevOps | ✅ | `docker-compose.prod.yml`, `docs/stages/stage4_consumer_run.md`; `swipe_consumer` и `match_consumer` подняты стендово и healthy |

**Приёмка:** закрыта. Кодовые замечания закрыты; base+prod стек поднят,
healthcheck отдельных consumer-сервисов подтверждён.

---

## Блок 3.4 — Расширение Celery (приоритет: средний)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| 3.4.1 | Точечный пересчёт рейтинга (вместо полного ночного) | Backend | ✅ | `backend/tasks/rating_tasks.py`, триггер из swipe |
| 3.4.2 | Асинхронная обработка загруженного фото (валидация/превью) | Backend | ✅ | `backend/tasks/photo_tasks.py`; Pillow validate + 512x512 JPEG thumbnail upload + moderation status |
| 3.4.3 | Асинхронная отправка push-уведомлений о мэтчах | Backend | ✅ | `backend/tasks/notification_tasks.py`, `bot/workers/match_consumer.py`, endpoint lookup telegram_id добавлен |
| 3.4.4 | Триггерить новые tasks из HTTP-эндпойнтов | Backend | ✅ | `backend/api/v1/matching.py`, `backend/api/v1/photos.py` |

**Приёмка:** закрыта локальной кодовой проверкой; runtime worker-прогон можно
добавить в финальную стендовую проверку.

---

## Блок 3.5 — Метрики и наблюдаемость (приоритет: средний)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| 3.5.1 | Бизнес-метрики backend (свайпы, мэтчи, длительности, cache hit/miss, ошибки MQ) | Backend | ✅ | `backend/core/metrics.py`, `backend/api/v1/matching.py`; swipe/match/MQ/cache metrics подключены и видны в `/metrics` |
| 3.5.2 | `/metrics` endpoint бота + метрики (сообщения, callbacks, ошибки API, доставка пушей, FSM) | Bot | ✅ | `bot/metrics.py`, `bot/api_client.py`, `bot/middlewares/auth.py`, `bot/workers/match_consumer.py`; метрики видны на `:8001/metrics` |
| 3.5.3 | Scrape бота в Prometheus | DevOps | ✅ | `infrastructure/prometheus/prometheus.yml` |
| 3.5.4 | Бизнес-панели в Grafana (свайпы, мэтчи, очереди RabbitMQ, hit ratio, ошибки MQ, активность бота) | DevOps | ✅ | `connectme.json`; backend/bot metrics теперь питаются данными |

**Приёмка:** закрыта локальной runtime-проверкой `/metrics` backend и bot.

---

## Блок 3.6 — Отчёт по этапу 4 (приоритет: низкий)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| 3.6.1 | Скелет отчёта по аналогии со stage1–3 | DevOps | ✅ | `docs/stages/stage4_report.md` |
| 3.6.2 | Разделы по своей зоне ответственности | Backend / Bot / Queue-Cache | ✅ | `docs/stages/stage4_report.md` обновлён без TODO по исправленным Auditor-пунктам |
| 3.6.3 | Раздел про CI/CD, нагрузку, мониторинг | DevOps | ✅ | `docs/stages/stage4_report.md`; добавлены endpoint-focused SLA, Grafana screenshot и consumer runtime check |
| 3.6.4 | Сверка `tracking_table.md` с фактическим состоянием | DevOps | ✅ | `tracking_table.md` больше не заявляет полный load SLA, указан малый прогон и остаток |

**Приёмка:** закрыта. Документ обновлён фактическими результатами; финальный
аудит создан.

---

## Блок 3.7 — Безопасность compose (приоритет: низкий)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| 3.7.1 | Убрать дефолты у чувствительных переменных в compose-файлах | DevOps | ✅ | `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.infra.yml` |
| 3.7.2 | `.env.example` оставить только placeholder'ами | DevOps | ✅ | `.env.example` |
| 3.7.3 | Прогнать поиск секретов в репозитории | DevOps | ✅ | `gitleaks detect --source /repo --redact` — no leaks found; grep по известным старым значениям чистый |
| 3.7.4 | Раздел про `.env` в README | DevOps | ✅ | `README.md` |

**Приёмка:** закрыта локальной проверкой compose config и gitleaks.

---

## Блок 3.8 — Singleton клиенты (приоритет: средний)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| 3.8.1 | MinIO-клиент создаётся один раз и переиспользуется | Backend | ✅ | `backend/core/minio.py`, `backend/services/photo_service.py` |
| 3.8.2 | Долгоживущий publisher событий вместо коннекта на каждый запрос | Queue/Cache | ✅ | `backend/core/mq.py`, `infrastructure/rabbitmq/event_publisher.py` |
| 3.8.3 | Fail-safe публикация (HTTP 200 не зависит от RabbitMQ) | Backend | ✅ | `backend/core/mq.py`, `backend/api/v1/matching.py` |

**Приёмка:** кодово закрыта и подтверждена малым swipe-flow/Locust-прогоном.

---

## Блок 3.9 — Топология RabbitMQ декларируется один раз (приоритет: средний)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| 3.9.1 | Развести «настройку топологии» и «горячий путь публикации» | Queue/Cache | ✅ | `infrastructure/rabbitmq/event_publisher.py` |
| 3.9.2 | Авто-reconnect и корректный shutdown | Queue/Cache | ✅ | `aio_pika.connect_robust`, `close_event_publisher()`, consumer shutdown |

**Приёмка:** кодово закрыта; RabbitMQ queues/DLQ видны на стенде.

---

## Блок 3.10 — Контекстное логирование (приоритет: низкий)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| 3.10.1 | Бизнес-логи backend содержат идентификаторы сущностей (user/match/photo) | Backend | 🟡 | Patcher и helper есть, но массовая адопция `logger.bind(...)` по backend не завершена |
| 3.10.2 | Бизнес-логи бота содержат `telegram_id` и контекст ошибки | Bot | 🟡 | `telegram_id` добавлен в auth middleware, но остальные handlers/API errors не покрыты системно |

**Приёмка:** частично. Инфраструктура логирования есть, покрытие кода неполное.

---

## Блок Доп — Чистка репозитория (приоритет: низкий)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| Д.1 | Удалить мусорные артефакты из git (логи, `.venv`, кэши) | DevOps | ✅ | `git ls-files` не показывает `.venv`, `.log`, `__pycache__`, `.pyc` |
| Д.2 | Обновить `.gitignore` под фактическую структуру | DevOps | ✅ | `.gitignore` |

**Приёмка:** закрыта для git-индекса. Локальные untracked runtime-файлы на диске не являются tracked-мусором.

---

## Блок Аудит — Верификация фиксов (приоритет: высокий)

| № | Задача | Исполнитель | Статус | Артефакт |
|---|--------|-------------|--------|----------|
| А.1 | Повторный аудит после быстрых фиксов (Фаза 1) | Auditor | ✅ | Этот файл: `promts/data/plan-fix/tracking-fix.md` |
| А.2 | Повторный аудит после функциональных фиксов (Фаза 2) | Auditor | ✅ | `promts/data/plan-fix/audit-round-3.md` |
| А.3 | Финальный аудит после нагрузки и отчёта (Фаза 3) | Auditor | ✅ | `promts/data/plan-fix/audit-final.md` |
| А.4 | Таблица «требование -> балл до/после» | Auditor | ✅ | `promts/data/plan-fix/audit-final.md` |

**Приёмка:** закрыта; финальный аудит фиксирует ожидаемый результат 30+ баллов
при зачёте notification-сервиса как дополнительного этапа.

---

## Сводка

| Блок | Задач | Готово | Частично | Нужно доработать/заблокировано | В очереди |
|------|------:|------:|---------:|-------------------------------:|----------:|
| 3.1 CI/CD | 4 | 4 | 0 | 0 | 0 |
| 3.2 Нагрузка | 6 | 5 | 1 | 0 | 0 |
| 3.3 Consumer'ы | 5 | 5 | 0 | 0 | 0 |
| 3.4 Celery | 4 | 4 | 0 | 0 | 0 |
| 3.5 Метрики | 4 | 4 | 0 | 0 | 0 |
| 3.6 Отчёт | 4 | 4 | 0 | 0 | 0 |
| 3.7 Compose secrets | 4 | 4 | 0 | 0 | 0 |
| 3.8 Singleton | 3 | 3 | 0 | 0 | 0 |
| 3.9 Топология MQ | 2 | 2 | 0 | 0 | 0 |
| 3.10 Логи | 2 | 0 | 2 | 0 | 0 |
| Доп | 2 | 2 | 0 | 0 | 0 |
| Аудит | 4 | 4 | 0 | 0 | 0 |
| **Итого** | **44** | **41** | **3** | **0** | **0** |

| Метрика | Значение |
|---------|----------|
| Всего задач | 44 |
| Выполнено | 41 |
| Частично выполнено | 3 |
| Нужно доработать/заблокировано | 0 |
| В очереди | 3 |
| Прогресс по полностью закрытым задачам | **93 %** |

---

## Финальные критерии готовности этапа 4

- [x] CI зелёный локально — `ruff` проходит, `pytest` 67 passed.
- [x] План и отчёт по нагрузке заполнены verification/full/stress/endpoint-focused SLA run.
- [x] RabbitMQ topology/DLQ видны на стенде; prod consumer healthcheck подтверждён base+prod запуском.
- [x] Celery вызывается из горячего пути API; фото/push tasks доработаны.
- [x] Grafana показывает бизнес-метрики и метрики бота; метрики теперь питаются.
- [x] Compose без дефолтных значений у секретов; gitleaks no leaks found.
- [x] `stage4_report.md` сведён по исправленным Auditor-пунктам.
- [x] `audit-final.md` подтверждает закрытие финальных пунктов и ожидаемые 30+ баллов.

**Текущий вывод после доработок:** блокирующие замечания аудитора исправлены.
Перед финальной защитой остаются только внешние подтверждения: фактический
GitHub Actions после push/PR и PM-зачёт Locust/notification-сервиса.

---

## Обозначения статусов

⬜ в очереди · 🟡 частично/требует доработки · ✅ выполнено · ❌ не выполнено/блокирует приёмку

---

*Обновлено аудитором на основе фактической проверки от 2026-05-11.*
