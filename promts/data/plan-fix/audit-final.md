# Финальный аудит Stage4

**Дата:** 2026-05-11
**Ветка:** `stage4`
**Источник:** `promts/data/plan-fix/tracking-fix.md`, `promts/requirements/req.md`

## Итог

Stage4 доведён до состояния защиты: CI-конфиг есть, локальные lint/tests/build
подтверждены, нагрузочные CSV и Grafana screenshot приложены, prod consumer'ы
подняты стендово и healthy, финальные DevOps-расхождения из `audit-round-3.md`
закрыты.

Ожидаемый балл по `req.md`: **30+** при зачёте notification-flow как
дополнительного этапа продукта (`match_notifications` -> bot consumer ->
Telegram push).

## Проверенные финальные артефакты

- `README.md` — CI-бейдж больше не ведёт на сторонний Actions URL.
- `docker-compose.prod.yml` — `swipe_consumer` и `match_consumer` с рабочим
  healthcheck без зависимости от `pgrep`.
- `docs/stages/stage4_consumer_run.md` — стендовый запуск consumer'ов.
- `docs/stages/stage4_loadtest.md` — mixed + endpoint-focused Locust results,
  p95/p99, bottleneck и Grafana screenshot.
- `docs/stages/img/stage4_load_grafana.png` — dashboard screenshot.
- `tests/load/locustfile_endpoint.py` — профиль 50+ RPS на отдельный endpoint.
- `tests/load/results/endpoint_next_stats.csv` — 3018 requests, 0 failures,
  51.07 RPS, p95=170 ms.
- `tests/load/results/endpoint_swipe_stats.csv` — 3067 requests, 0 failures,
  51.87 RPS, p95=81 ms.

## Таблица баллов

| Требование `req.md` | До фиксов | После фиксов | Основание |
|---|---:|---:|---|
| Рейтинг | 3 | 3 | multi-level rating уже реализован |
| Redis | 2 | 2 | profile session cache, hot matching path |
| Celery | 1 | 2 | rating/photo/notification tasks, HTTP triggers |
| RabbitMQ | 1 | 2 | publisher + consumers + DLQ/retry |
| Метрики и логирование | 1 | 2 | backend/bot `/metrics`, Grafana, contextual logs частично |
| S3/MinIO | 2 | 2 | photo storage + thumbnail pipeline |
| CI/CD | 0 | 1 | GitHub Actions lint/tests/build/gitleaks |
| Этапы продукта, базовые | 15 | 15 | planning, base functionality, анкеты/ranking, DB, bot |
| Нагрузочное тестирование | 0 | 1 | Locust CSV + report + Grafana screenshot |
| Доп. этап: notification service | 0 | 2-3 | async match push через RabbitMQ consumer (док: `docs/stages/stage_notification_service.md`) |

Консервативная сумма: **31** (если notification-flow засчитать на 2 балла).
При полном зачёте notification-сервиса: **32**. Даже без максимального зачёта
получается порог оценки «5» (**30+**).

## Остаточные риски

- GitHub Actions формально подтвердится только после push/PR в удалённый repo.
- Locust вместо JMeter требует PM-зачёта, хотя в `tests/load/README.md`
  и stage4 report он задокументирован как согласованная альтернатива.
- При aggressive setup через `/matching/next` на 80+ RPS PostgreSQL упирается
  в `TooManyConnectionsError`; финальный endpoint-focused профиль обходит setup
  и показывает фактическую пропускную способность самих critical endpoints.

## Решение аудитора

Финальный статус Stage4: **готово к защите**.
