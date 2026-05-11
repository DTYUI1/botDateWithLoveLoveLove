# Задачи по агентам — план фиксов ConnectMe (этап 4)

**Источник:** `promts/data/plan-fix/plan-fix.md`
**Дата:** 2026-05-11
**Ветка:** `stage4`
**PM-роль:** распределение работ из аудита по существующим агентам.

## Карта агентов проекта

| Агент | Файл промта | Зона ответственности |
|-------|-------------|----------------------|
| Backend Developer | `promts/backend_developer.md` | FastAPI, SQLAlchemy, бизнес-логика, Celery tasks, метрики backend |
| Queue & Cache Engineer | `promts/queue_cache_engineer.md` | Redis, RabbitMQ (брокер + consumer'ы), MinIO, PostgreSQL-инфра |
| Telegram Bot Developer | `promts/telegram_bot_developer.md` | aiogram 3, UX, FSM, consumer уведомлений в боте |
| DevOps | `promts/devops.md` | Docker, CI/CD, secrets, нагрузочные тесты, Prometheus/Grafana, отчёты |
| Auditor | `promts/auditor.md` | Read-only аудит, верификация фиксов |

## Сводка распределения по разделам plan-fix.md

| # | Проблема | Приоритет | Ответственные |
|---|----------|-----------|---------------|
| 3.1 | Нет CI/CD | высокий | DevOps |
| 3.2 | Нет нагрузочного тестирования | высокий | DevOps (план) + Backend (стенд) |
| 3.3 | RabbitMQ без consumer'ов | средний | Queue/Cache (инфра + rating_consumer) + Bot (notification_consumer) + Backend (точки публикации) |
| 3.4 | Celery — одна ночная задача | средний | Backend (`.delay()` вызовы и новые tasks) + Queue/Cache (брокер/инфра) |
| 3.5 | Метрики неполные | средний | Backend (бизнес-метрики API) + Bot (`/metrics`) + DevOps (Grafana, prometheus.yml) |
| 3.6 | Нет отчёта stage4 | низкий | DevOps (структура) + Backend + Bot + Queue/Cache (свои разделы) |
| 3.7 | Дефолтные секреты в compose | низкий | DevOps |
| 3.8 | MinIOClient/EventPublisher без singleton | средний | Backend (MinIOClient) + Queue/Cache (EventPublisher) |
| 3.9 | EventPublisher declare на каждый запрос | средний | Queue/Cache |
| 3.10 | Бизнес-логи без контекста | низкий | Backend + Bot |

## Файлы с детальными задачами

- [tasks-backend-developer.md](tasks-backend-developer.md) — задачи для backend-разработчика
- [tasks-queue-cache-engineer.md](tasks-queue-cache-engineer.md) — задачи для инфраструктурного инженера (брокеры/кэш)
- [tasks-telegram-bot-developer.md](tasks-telegram-bot-developer.md) — задачи для бота
- [tasks-devops.md](tasks-devops.md) — задачи DevOps
- [tasks-auditor.md](tasks-auditor.md) — задачи аудитора

## Порядок выполнения (рекомендация PM)

**Фаза 1 — параллельно (быстрые баллы):**
- DevOps: 3.1 CI/CD, 3.7 secrets cleanup.
- Queue/Cache: 3.8/3.9 рефактор `EventPublisher` (singleton + setup_topology).
- Backend: 3.8 MinIOClient singleton, 3.10 контекстные логи.

**Фаза 2 — последовательно (зависит от Фазы 1):**
- Queue/Cache: 3.3 базовый consumer-фреймворк, объявление сервисов.
- Backend: 3.4 новые Celery-tasks (`recalculate_user_rating`, `process_uploaded_photo`, `send_match_notification`), вызовы `.delay()`.
- Bot: 3.3 `notification_consumer` для `match_notifications`.
- Backend: 3.5 бизнес-метрики (`swipes_total`, `matches_total`, …).
- Bot: 3.5 `/metrics` aiohttp endpoint.

**Фаза 3 — после Фазы 2:**
- DevOps: 3.5 Grafana панели + scrape-target бота, 3.2 нагрузочное тестирование, 3.6 stage4_report.
- Auditor: повторный аудит, проверка соответствия требованиям.

## Acceptance — общая метрика «готовности этапа»

Этап 4 считается полностью закрытым, когда:
1. CI зелёный (lint + tests + docker build) на push в `stage4` и PR в `main`.
2. Есть `.jmx`/Locust план в `tests/load/`, прогнан, отчёт в `docs/stages/stage4_loadtest.md`.
3. Хотя бы один RabbitMQ-consumer обрабатывает реальные события (нет роста длины очередей в Grafana под нагрузкой).
4. Celery вызывается из HTTP-пути минимум для 1 операции (`.delay()` в коде backend).
5. Grafana дашборд показывает `swipes_total`, `matches_total`, длину очередей.
6. `docker-compose.yml` не имеет дефолтных значений у `POSTGRES_PASSWORD`, `MINIO_*`, `RABBITMQ_PASSWORD`.
7. `docs/stages/stage4_report.md` создан и согласован.
8. Auditor подтвердил закрытие пунктов 3.1–3.10 повторным прогоном.
