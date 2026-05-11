# Задачи для DevOps

**Промт агента:** `promts/devops.md`
**Источник несоответствий:** `promts/data/plan-fix/plan-fix.md`
**Ветка:** `stage4`

## Контекст

Базовая инфраструктура есть: `docker-compose.yml`, `docker-compose.prod.yml`, `scripts/deploy.sh`, Prometheus + Grafana, RabbitMQ-exporter, бэкап-скрипт. НО критичные DevOps-пункты системы оценивания не закрыты:
- **CI/CD отсутствует полностью** — нет `.github/workflows/`, нет `Jenkinsfile` (потеря до 1 балла, дешевле всего закрыть).
- **Нагрузочного теста нет** — нужен JMeter-план или согласованная альтернатива (Locust/k6).
- **Grafana** показывает только HTTP backend, нет бизнес-метрик и метрик бота.
- **Дефолтные секреты** в compose-файлах (публичные dev-default fallback значения).
- **Отчёт по этапу 4** не создан (`docs/stages/stage4_report.md`).
- **Consumer-сервисы** ещё не упакованы (зависимость от Bot/Backend).

Твоя задача — закрыть всё «инфраструктурное» вокруг функциональных фиксов остальных агентов.

---

## T-D1. CI/CD pipeline (раздел 3.1) — **ВЫСОКИЙ ПРИОРИТЕТ**

**Файлы:** `.github/workflows/ci.yml` (новый), опционально `.github/workflows/release.yml`.

**Что сделать:**

**Workflow `ci.yml`** — триггеры `push` (любая ветка) и `pull_request` в `main`:

| Job | Шаги | Условие |
|-----|------|---------|
| `lint` | checkout → setup-python 3.11 → `pip install ruff` → `ruff check backend bot infrastructure` | всегда |
| `tests` | checkout → setup-python 3.11 → `pip install -r requirements.txt` → `pytest tests/ -v` | всегда |
| `compose-validate` | checkout → `docker compose -f docker-compose.yml config -q` → `docker compose -f docker-compose.prod.yml config -q` | всегда |
| `docker-build` | matrix `[backend, bot]` → `docker build -f <service>/Dockerfile .` | только на push в `main` или PR |
| `security-scan` | `trufflehog filesystem .` (поиск секретов в diff) | на PR |

**Acceptance:**
- Workflow зелёный на текущей ветке `stage4`.
- Бейдж CI добавлен в `README.md`.
- PR в `main` блокирует merge при упавших `lint` или `tests` (через required status checks — отметить в `docs/stages/stage4_report.md`).

**Приоритет:** высокий. **Оценка:** 3–4 ч.

---

## T-D2. Нагрузочное тестирование (раздел 3.2) — **ВЫСОКИЙ ПРИОРИТЕТ**

**Файлы:**
- `tests/load/connectme.jmx` (JMeter) или `tests/load/locustfile.py` (Locust) — на выбор после уточнения с PM.
- `tests/load/results/` — артефакты прогона.
- `docs/stages/stage4_loadtest.md` — итоговый отчёт.

**Что покрыть:**
1. `POST /api/v1/auth/telegram` — 50 RPS, 5 минут.
2. `GET /api/v1/matching/next` — 200 RPS, 10 минут (горячий путь, проверяет Redis-кэш).
3. `POST /api/v1/matching/swipe` — 100 RPS, 10 минут (проверяет RabbitMQ-publisher).

**Перед прогоном:**
- Засидить БД через `scripts/seed_mock_users.py` (как минимум 10 000 профилей — иначе подбор будет аномальным).
- Убедиться, что задачи T-B1/T-B2/T-Q1 завершены (иначе MinIO/MQ станут bottleneck'ом).

**Отчёт `stage4_loadtest.md`:**
- Краткое резюме сценариев.
- Скриншоты графиков (RPS, p95, error rate) — из Grafana или JMeter HTML report.
- Найденные узкие места и рекомендации.
- Сравнение «до/после» (хотя бы один до-фикса прогон для базовой линии).

**Acceptance:**
- При 200 RPS на `/matching/next` p95 < 200 мс, ошибок < 0.5%.
- При 100 RPS на `/matching/swipe` `rabbitmq_queue_messages_ready{queue="swipe_processing"}` не растёт линейно (т.е. consumer T-B5 справляется).
- Отчёт коммитнут в репозиторий.

**Перед стартом задачи** — уточнить у PM: JMeter обязателен или Locust/k6 принимается (см. раздел 5 plan-fix.md).

**Приоритет:** высокий. **Оценка:** 6–8 ч.

---

## T-D3. Расширение Grafana и Prometheus (раздел 3.5)

**Файлы:**
- `infrastructure/prometheus/prometheus.yml` — добавить scrape-target.
- `infrastructure/grafana/provisioning/dashboards/connectme.json` — обновить дашборд.

**Что сделать:**
1. В `prometheus.yml` добавить scrape job для бота:
   ```yaml
   - job_name: 'bot'
     static_configs:
       - targets: ['bot:9100']
   ```
2. В дашборд `connectme.json` добавить панели (зависит от T-B4 / T-T2):
   - «Свайпы в минуту» — `rate(swipes_total[1m])` по `action`.
   - «Мэтчи в минуту» — `rate(matches_total[1m])`.
   - «Длина очередей RabbitMQ» — `rabbitmq_queue_messages_ready{queue=~"swipe_processing|match_notifications|rating_calculation|message_delivery"}`.
   - «Cache hit ratio» — `rate(cache_lookups_total{result="hit"}[5m]) / rate(cache_lookups_total[5m])`.
   - «Bot callbacks/min» — `rate(bot_callbacks_total[1m])` по `action`.
   - «MQ publish failures» — `rate(mq_publish_failed_total[5m])`.
3. Импортировать готовые RabbitMQ-dashboards (id 10991) и Redis (id 763) для базовой инфраструктуры.

**Acceptance:**
- Открыть Grafana, дашборд `ConnectMe` показывает все 6 новых панелей.
- Под нагрузочным тестом T-D2 значения метрик корректные.

**Приоритет:** средний. **Зависимости:** T-B4, T-T2.

---

## T-D4. Cleanup дефолтных секретов в compose (раздел 3.7)

**Файлы:** `docker-compose.yml:31-36`, `docker-compose.prod.yml`, `.env.example`.

**Что сделать:**
1. Везде, где у чувствительных переменных есть fallback — заменить на `${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}` и аналогичные required-подстановки.
2. То же для `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS`, `TELEGRAM_BOT_TOKEN`, `SECRET_KEY`.
3. `.env.example` оставить с явными placeholder'ами `change_me_*`, без боевых значений.
4. Прогнать `trufflehog filesystem .` и убедиться, что secrets в git-истории нет (если есть — обсудить с PM force-rewrite вопрос).
5. README: добавить раздел «Как заполнить `.env`».

**Acceptance:**
- `docker compose config` без `.env` падает с понятной ошибкой «POSTGRES_PASSWORD is required».
- `trufflehog` зелёный на текущем коммите.
- README содержит инструкцию.

**Приоритет:** низкий (без баллов, но хорошая практика).

---

## T-D5. Чистка репозитория от мусора (раздел 5 plan-fix.md)

**Что сделать:**
- Удалить из git `bot_nohup.log` (296 KB), `.venv/`, `practice/p4/.venv/` (Python 3.14 конфликт), `__pycache__/`.
- Обновить `.gitignore`:
  ```
  *.log
  .venv/
  practice/*/.venv/
  __pycache__/
  *.pyc
  .pytest_cache/
  ```
- В CI workflow добавить `pre-commit` hook или ruff-check на эти артефакты.

**Acceptance:**
- `git ls-files | grep -E "\.venv|\.log|__pycache__"` возвращает 0 строк.

**Приоритет:** низкий.

---

## T-D6. Docker-сервисы для consumer'ов (раздел 3.3)

**Зависимость:** T-T1 (bot/workers/notification_consumer.py) и T-B5 (backend/workers/rating_consumer.py) должны быть готовы.

**Что сделать в `docker-compose.yml` и `docker-compose.prod.yml`:**

```yaml
bot_notification_consumer:
  build: ./bot
  command: python -m bot.workers.notification_consumer
  depends_on: [rabbitmq, backend]
  env_file: .env
  restart: unless-stopped

backend_rating_consumer:
  build: ./backend
  command: python -m backend.workers.rating_consumer
  depends_on: [rabbitmq, celery_worker]
  env_file: .env
  restart: unless-stopped
```

Также проверить `celery_worker` и `celery_beat` (уже есть, но убедиться, что `restart: unless-stopped`).

**Acceptance:**
- `docker compose ps` показывает 2 новых здоровых сервиса.
- Логи consumer'ов в stdout, видны через `docker compose logs -f bot_notification_consumer`.

**Приоритет:** средний.

---

## T-D7. Stage 4 report (раздел 3.6)

**Файл:** `docs/stages/stage4_report.md`.

**Что сделать:**
- Создать скелет по аналогии с `stage1_report.md`, `stage2_report.md`, `stage3_report.md`.
- Разделы:
  1. Введение / цель этапа.
  2. Выполненные задачи (по `tracking_table.md` 4.1–4.8).
  3. Архитектурные решения этапа (Celery, RabbitMQ consumers, MinIO, метрики).
  4. CI/CD (раздел DevOps).
  5. Нагрузочное тестирование (короткая выжимка из `stage4_loadtest.md` + ссылка).
  6. Метрики и мониторинг (скриншоты Grafana).
  7. Ссылки на смежные документы.
- Скоординировать с Backend / Bot / Queue/Cache, чтобы они заполнили свои разделы (T-B7, T-T5, T-Q6).

**Acceptance:**
- Файл создан, ссылается на `stage4_loadtest.md`, на CI-workflow, на дашборд.
- `tracking_table.md` соответствует фактическому состоянию (этап 4 закрыт).

**Приоритет:** низкий (последний шаг перед сдачей этапа).

---

## T-D8. Healthcheck для новых сервисов

После T-D6 убедиться, что для consumer'ов в `docker-compose.yml` прописаны healthcheck'и (как минимум проверка ребута процесса):

```yaml
healthcheck:
  test: ["CMD", "pgrep", "-f", "notification_consumer"]
  interval: 30s
  timeout: 5s
  retries: 3
```

Это нужно, чтобы при падении consumer'а compose рестартовал сервис.

**Приоритет:** низкий.

---

## Что НЕ входит в зону DevOps

- Бизнес-логика consumer'ов и tasks → Backend / Bot.
- Реализация бизнес-метрик в коде (`Counter`, `Histogram`) → Backend / Bot. DevOps только настраивает scrape и дашборд.
- Рефакторинг `EventPublisher` → Queue/Cache Engineer.

## Definition of Done для DevOps

- [ ] T-D1: CI workflow зелёный.
- [ ] T-D2: JMeter/Locust план + отчёт `stage4_loadtest.md`.
- [ ] T-D3: Grafana дашборд показывает бизнес-метрики и RabbitMQ.
- [ ] T-D4: дефолты секретов убраны, README обновлён.
- [ ] T-D5: репозиторий очищен от `.venv/`, `*.log`, `__pycache__/`.
- [ ] T-D6: consumer-сервисы в `docker-compose.yml` и работают.
- [ ] T-D7: `stage4_report.md` сведён воедино.
- [ ] T-D8: healthcheck для consumer'ов.

## Отчёт

После каждой DevOps-задачи обновить `data/devops-report/devops-report.md` (формат — в `promts/devops.md`, раздел «Отчёт после выполнения»).
