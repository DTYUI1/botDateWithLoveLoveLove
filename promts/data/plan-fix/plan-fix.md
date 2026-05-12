# План доработки проекта

**Источник требований:** `promts/requirements/req.md`
**Дата аудита:** 2026-05-12
**Ветка:** `stage4`
**Предыдущие итерации:** `audit-round-3.md`, `audit-final.md`, `tracking-fix.md`

---

## 1. Краткое резюме

Проект ConnectMe фактически закрыл всю основную часть требований
`req.md`: Redis (сессии + рейтинг), Celery (rating / photo / notification
+ HTTP-триггеры), RabbitMQ (publisher + 2 consumer'а + DLQ),
MinIO (singleton + thumbnail), GitHub Actions CI (lint / tests / build /
gitleaks), бизнес-метрики backend и бота, Grafana-дашборд с 22 панелями,
Locust mixed + endpoint-focused SLA-прогоны, prod consumer'ы стендово
healthy. Финальный аудит `audit-final.md` фиксирует ожидаемый балл **30+**.

**Что осталось до защиты — три категории:**

1. **Доказательства работоспособности** (без них балл могут срезать
   ревьюверы независимо от кода): фактический зелёный run GitHub Actions
   на удалённом репозитории + дополнительные скриншоты Grafana (сейчас
   приложен только один общий скрин нагрузки — `stage4_load_grafana.png`).
2. **PM-зачёт нестандартных решений**: Locust вместо Apache JMeter (по
   `req.md` п.20 — «если в другом формате, обговариваем лично»),
   notification-сервис как доп. этап (по п.21).
3. **Хвосты внутри кода**: неполная адопция контекстного логирования
   (`logger.bind` — 16 точек на 37 точек инициализации логгера),
   `TooManyConnectionsError` PostgreSQL под aggressive setup при 80+ RPS
   (потенциальный риск, который ревьюверы могут попросить проверить).

Эти три категории не блокируют сборку, но напрямую влияют на пункты
рейтинга «Метрики и логирование» (п.5) и «CI/CD» (п.7), а также на
страховой запас баллов сверх 30.

---

## 2. Проверенные требования

### Основная часть (req.md п.1–8)

- [x] **Рейтинг (multi-level)** — `backend/services/rating_service.py`,
      Sorted Set в Redis, дневные счётчики, beat пересчёт + точечный
      пересчёт из swipe-consumer. Уровни — есть.
- [x] **Redis (обоснованное применение)** — `backend/core/redis_client.py`,
      `infrastructure/redis/cache_patterns.py` (ProfileSessionCache,
      RatingCache), используется в matching и rating сервисах.
      Не только для Celery → не штрафной случай.
- [x] **Celery** — `backend/celery_app.py`, `backend/tasks/{rating,photo,
      notification}_tasks.py`, `.delay()` из `api/v1/matching.py`,
      `api/v1/photos.py`. Используется на горячем пути.
- [x] **MQ-брокер (RabbitMQ)** — `infrastructure/rabbitmq/event_publisher.py`,
      singleton-publisher (`backend/core/mq.py`), consumer'ы
      `backend/workers/swipe_consumer.py` и `bot/workers/match_consumer.py`,
      DLQ в `infrastructure/rabbitmq/definitions.json`. Используется не
      только для Celery → не штрафной случай.
- [x] **Метрики и логирование (база)** — backend `/metrics` через
      `prometheus-fastapi-instrumentator` + бизнес-метрики
      `backend/core/metrics.py`; bot `/metrics` на :8001 через
      `bot/metrics.py`. Grafana-дашборд `connectme.json` (22 панели).
      Prometheus scrape backend/bot/rabbitmq.
- [?] **Метрики и логирование (зачёт «обоснованное применение» полностью)**
      — скриншот Grafana один (`stage4_load_grafana.png`, общий нагрузочный),
      не покрывает RabbitMQ, Bot, Cache hit ratio панели. Без них ревьюверу
      труднее увидеть, что метрики реально питаются.
- [x] **S3/MinIO** — `backend/core/minio.py` (singleton), фото-сервис,
      thumbnail в Celery (`photo_tasks.process_photo`).
- [?] **CI/CD** — `.github/workflows/ci.yml` есть, локально lint+pytest
      зелёные, gitleaks scan чистый. Но фактического push'а в GitHub и
      реального run на GH Actions в репозитории нет → ревьюверу нечего
      открыть, чтобы убедиться. См. `audit-final.md` секция «Остаточные
      риски».

### Этапы продукта (req.md п.9)

- [x] **Этап 1 — Планирование/проектирование** — `docs/stages/stage1_report.md`,
      `prd.json`, `architecture.json`, `dbdiagram.dbml`.
- [x] **Этап 2 — Базовый функционал** — `docs/stages/stage2_report.md`,
      bot handlers / FastAPI endpoints.
- [x] **Этап 3 — Анкеты и ранжирование** — `docs/stages/stage3_report.md`,
      rating service + Redis + matching.
- [x] **БД настроена и работает** — Postgres + Alembic-миграции,
      `backend/models/*`.
- [x] **Бот работает, ручные тесты выдерживает** — подтверждено
      `bot_nohup.log`, `test_bot.py`, тестовый пользователь Яр.
- [?] **Нагрузочное тестирование Apache JMeter** — формально JMeter не
      использован. В `docs/stages/stage4_loadtest.md` Locust назван
      «согласованной альтернативой», но письменного PM-зачёта в репозитории
      нет.
- [?] **Доп. этап: notification-сервис** — `bot/workers/match_consumer.py`
      + `backend/tasks/notification_tasks.py` + endpoint
      `/api/v1/profile/{id}/telegram_id`. Полноценный async-push pipeline.
      Тоже требует явного PM-зачёта по п.21 («Другой этап… обговариваем
      лично»).

---

## 3. Найденные несоответствия

### 3.1 Один общий скриншот Grafana вместо набора по доменам

- **Требование:** п.5 «Метрики и логирование. Любое обоснованное
  применение» (0–2 балла).
- **Текущее состояние:** дашборд `connectme.json` содержит 22 панели
  (RPS, p95, 5xx, inflight, swipes/min, matches/min, swipe duration p95,
  cache hit ratio, RMQ queue depth, DLQ depth, MQ publish ok/errors,
  bot updates, callbacks, push delivery, bot API errors). В отчёте
  приложен только один общий снимок `docs/stages/img/stage4_load_grafana.png`
  — это снимок во время нагрузочного прогона, по нему невозможно
  отдельно увидеть RabbitMQ / Bot / Cache hit ratio панели.
- **Где обнаружено:** `docs/stages/img/`, `docs/stages/stage4_loadtest.md`,
  `docs/stages/stage4_report.md`.
- **Что нужно сделать:** при поднятом stack’е и небольшой live-нагрузке
  снять 4 дополнительных скриншота и положить в `docs/stages/img/`:
  1. `stage4_grafana_business.png` — секция «Бизнес-метрики» (свайпы/мин,
     мэтчи/мин, swipe p95, cache hit ratio).
  2. `stage4_grafana_rabbitmq.png` — секция «RabbitMQ» (queue depth, DLQ,
     publish ok/errors).
  3. `stage4_grafana_bot.png` — секция «Bot» (kind updates, callbacks/min,
     push delivery, API errors).
  4. `stage4_grafana_http.png` — общая HTTP-секция (RPS, p95, 5xx,
     inflight) под live-трафиком.
  Вставить ссылки в `docs/stages/stage4_loadtest.md` (раздел 5) и
  `docs/stages/stage4_report.md` (блок 3.5).
- **Приоритет:** высокий (пользователь явно указал, что нужны метрики
  и скрины).

### 3.2 Нет фактического зелёного run в GitHub Actions

- **Требование:** п.7 «Настройка CI/CD для бота. CI/CD, Jenkins, Github
  Actions. Любое обоснованное применение» (0–1 балл).
- **Текущее состояние:** `.github/workflows/ci.yml` сконфигурирован
  (4 jobs: lint / tests / build-images / secret-scan), README содержит
  CI-бейдж. Но коммитов на remote (origin) нет: последние коммиты —
  локальные `8d1a72a hot fix 0.5`, `d704458 4 этап`. Ревьюверу нечего
  открыть.
- **Где обнаружено:** `git log`, `README.md` (бейдж ведёт на путь
  workflow относительно репозитория, который у ревьювера не будет).
- **Что нужно сделать:**
  1. Запушить ветку `stage4` в origin (или открыть PR в `main`),
     дождаться зелёного workflow run.
  2. Сделать скриншот вкладки Actions (или зелёного бейджа на странице
     PR) и положить в `docs/stages/img/stage4_ci_green.png`.
  3. Зафиксировать ссылку на конкретный run в `audit-final.md`.
- **Приоритет:** высокий.

### 3.3 Locust vs JMeter — нет формального PM-зачёта

- **Требование:** п.20 «Проведение нагрузочного тестирования с помощью
  Apache JMeter, если в другом формате, обговариваем лично» (0–1 балл).
- **Текущее состояние:** Locust полностью реализован
  (`tests/load/locustfile.py`, `locustfile_endpoint.py`, 5 групп CSV-
  артефактов, отчёт с p95/p99). В `stage4_loadtest.md` написано
  «согласовано как замена JMeter», но письменной формальной апрувы PM
  в репозитории нет.
- **Где обнаружено:** `docs/stages/stage4_loadtest.md` (строка 4),
  `tests/load/README.md`.
- **Что нужно сделать:** получить от PM явное подтверждение (комментарий
  в чате/issue/Slack), сохранить скриншот или цитату в
  `docs/stages/stage4_loadtest.md` (новый раздел «Согласование с PM»)
  с датой и источником. Альтернативно — добавить минимальный
  `.jmx`-сценарий из 1–2 thread-group, прогнать, приложить
  `*_jmeter.jtl` и скриншот JMeter Summary Report для подстраховки.
- **Приоритет:** средний.

### 3.4 Notification-сервис как доп. этап — нет явной фиксации

- **Требование:** п.21 «Другой этап, обговариваем с вами лично. Пример:
  сервис notification и т. д.» (0–3 балла за каждый новый пункт).
- **Текущее состояние:** реализация есть (`backend/tasks/notification_tasks.py`,
  `bot/workers/match_consumer.py`, endpoint lookup telegram_id), но в
  отчётах он подаётся как «часть Celery + RMQ», а не отдельный этап.
  По `audit-final.md` это +2–3 балла, ради которых стоит явно оформить.
- **Где обнаружено:** `audit-final.md` (раздел «Таблица баллов» —
  notification-flow засчитан как доп. этап на 2 балла).
- **Что нужно сделать:** добавить в `docs/stages/` файл
  `stage_notification_service.md` (по аналогии со stage4): описание
  pipeline, точки входа, схема `swipe → match → backend
  notification_tasks → publish('match_notifications') → bot
  match_consumer → Telegram push`, метрики
  `bot_push_delivered_total` / `bot_push_failed_total`, end-to-end
  пример. Согласовать с PM, что этот сервис засчитывается как доп. этап.
- **Приоритет:** средний.

### 3.5 Контекстное логирование адоптировано частично

- **Требование:** п.5 «Метрики и Логирование. Любое обоснованное
  применение». В примерах req.md явно указано, что плохое логирование
  (без контекста) штрафное.
- **Текущее состояние:** `backend/core/logging_context.py` определяет
  хелперы `with_user/match/photo/profile`. `logger.bind(...)` встречается
  16 раз против 37 точек инициализации loguru-логгера → покрытие < 50%.
  В `tracking-fix.md` блок 3.10 помечен как 🟡 «адопция инкрементальная».
- **Где обнаружено:** `backend/core/logging_context.py`,
  `bot/middlewares/auth.py`, остальные handlers / API endpoints —
  логи без `bind`.
- **Что нужно сделать:** пройтись по `backend/api/v1/*.py` и
  `bot/handlers/*.py`, в каждом обработчике сделать первый `logger =
  with_user(telegram_id=...)` (или `with_profile`, `with_match`) и
  использовать его дальше. Без переписывания форматтера — это
  drop-in замена `logger` на `with_user(logger, ...)`. Достаточно
  закрыть top-N горячих обработчиков: `/auth/telegram`, `/profile`,
  `/matching/next`, `/matching/swipe`, `/photos/upload`, bot
  `cmd_start`, `cmd_profile`, `cmd_search`, `cmd_matches`. Ожидаемый
  эффект — каждая запись лога несёт `telegram_id=...` / `profile_id=...`,
  ревьюверу видно «обоснованность» п.5.
- **Приоритет:** средний.

### 3.6 PostgreSQL TooManyConnectionsError под aggressive setup

- **Требование:** п.5 «обоснованное применение» + п.20 «нагрузочное
  тестирование» (потенциально может срезать балл, если ревьювер
  попросит повторить).
- **Текущее состояние:** в `audit-final.md` раздел «Остаточные риски»
  и в `stage4_loadtest.md` (раздел 8) указано, что при aggressive setup
  через `/matching/next` на 80+ RPS Postgres упирается в
  `TooManyConnectionsError`. Решение известно (увеличить
  `max_connections` / поднять PgBouncer), но не применено.
- **Где обнаружено:** `docs/stages/stage4_loadtest.md` (раздел 8),
  `audit-final.md` (раздел «Остаточные риски»).
- **Что нужно сделать (по убыванию объёма):**
  1. **Минимум:** в `stage4_loadtest.md` явно пометить, что это
     observation, а не блокер; добавить таблицу «текущий потолок vs
     SLA».
  2. **Желательно:** поднять `max_connections` в
     `infrastructure/postgres/postgresql.conf` (или передать через
     compose env), повторить endpoint-focused прогон, обновить CSV.
  3. **По-настоящему:** добавить PgBouncer как отдельный compose-сервис
     (между backend и postgres). Это уже плановая работа, выходит за
     рамки stage4.
- **Приоритет:** низкий (только если ревьювер спросит).

---

## 4. План фикса

Порядок — от блокеров к страховке. Шаги 1–2 закрывают то, что
**пользователь явно назвал** (Grafana + скрины). Шаги 3–4 закрывают
PM-зависимые пункты. Шаги 5–6 — внутренние хвосты.

### Шаг 1. Снять полный набор скриншотов Grafana

1. Поднять весь стек: `docker compose -f docker-compose.yml -f
   docker-compose.prod.yml up -d`.
2. Запустить лёгкую live-нагрузку, чтобы панели заполнились данными,
   а не нулями:
   ```bash
   bash tests/load/seed.sh 100
   .venv/bin/python -m locust -f tests/load/locustfile.py \
     --host http://localhost:8005 --users 20 --spawn-rate 5 \
     --run-time 120s --headless
   ```
3. Параллельно сделать несколько свайпов из тестового аккаунта Яр
   (telegram_id=913011232) и пару загрузок фото, чтобы заполнились
   секции «Bot» и «Cache hit ratio».
4. Открыть Grafana (`http://localhost:3000`, креды из `.env`,
   dashboard «ConnectMe — Business + Infra») и снять 4 скриншота
   (PNG, не JPG, чтобы текст читался):
   - `docs/stages/img/stage4_grafana_business.png`
   - `docs/stages/img/stage4_grafana_rabbitmq.png`
   - `docs/stages/img/stage4_grafana_bot.png`
   - `docs/stages/img/stage4_grafana_http.png`
5. Вставить в `docs/stages/stage4_loadtest.md` раздел 5 (после
   существующего общего скрина) и в `docs/stages/stage4_report.md`
   блок 3.5 ссылки на все 4 файла с короткими подписями («Что видим:
   свайпы пошли, hit ratio ≈ X»).

### Шаг 2. Запушить CI и приложить зелёный run

1. `git add ... && git commit` оставшихся изменений (см. список untracked
   в `git status`) — особенно `audit-final.md`,
   `tests/load/locustfile_endpoint.py`, новые скриншоты из Шага 1.
2. `git push origin stage4` (или открыть PR `stage4 → main`).
3. Дождаться выполнения всех 4 jobs (`lint`, `tests`, `build-images`,
   `secret-scan`).
4. Снять скриншот успешного workflow run (страница
   `https://github.com/<owner>/<repo>/actions/runs/<id>`) →
   `docs/stages/img/stage4_ci_green.png`.
5. Добавить в `audit-final.md` раздел «GitHub Actions confirmation»
   с ссылкой на конкретный run и скриншотом.

### Шаг 3. Получить PM-зачёт Locust и notification-сервиса

1. Сформулировать запрос PM одним сообщением: «Locust засчитывается
   как эквивалент JMeter? Notification-сервис засчитывается как
   доп. этап продукта (п.21 req.md)?».
2. Сохранить ответ (скриншот / цитата) в новый файл
   `docs/stages/stage4_pm_approvals.md` с датой и источником.
3. Сослаться на этот файл из `stage4_loadtest.md` (раздел «Согласование
   с PM») и из `audit-final.md` (таблица баллов, строки «Locust» и
   «notification»).

### Шаг 4. Оформить notification-сервис как отдельный этап

1. Создать `docs/stages/stage_notification_service.md` со структурой:
   - Цель и сценарий (match → push).
   - Архитектура: backend `notification_tasks.py` → RMQ
     `match_notifications` → bot `match_consumer` → Telegram API.
   - Точки отказа и retry: DLQ, exponential backoff в base_consumer,
     метрики `bot_push_delivered_total` / `bot_push_failed_total`.
   - End-to-end ручной тест (telegram_id → ожидаемый push).
2. Сослаться на этот файл из `stage4_report.md` (новый раздел «Доп.
   этап продукта») и из `audit-final.md` (таблица баллов).

### Шаг 5. Адоптировать `logger.bind(...)` в горячих обработчиках

1. `backend/api/v1/matching.py`: в `next_profile` и `swipe`
   первой строкой `logger = with_user(logger, telegram_id=...)`.
2. То же для `auth.py`, `profile.py`, `photos.py`, `rating.py`.
3. `bot/handlers/profile.py`, `bot/handlers/search.py`,
   `bot/handlers/photos.py`, `bot/handlers/settings.py`: первой
   строкой обработчика `logger = with_user(logger,
   telegram_id=event.from_user.id)`.
4. Прогнать `pytest tests -q` чтобы убедиться, что patcher не
   падает на новых ключах.
5. Обновить блок 3.10 в `tracking-fix.md` с 🟡 на ✅.

### Шаг 6. Подстраховаться по PostgreSQL connection pool

1. **Минимально:** обновить `stage4_loadtest.md` раздел 6/8 — явно
   описать, что 80+ RPS aggressive setup упирается в `max_connections`
   и это уже за пределами целевого SLA stage4.
2. **Опционально (если время есть):** поднять `max_connections` до
   200 в `infrastructure/postgres/postgresql.conf` (или через
   `command:` в docker-compose), повторить endpoint-focused прогон
   (`tests/load/seed.sh 800 120 && LOCUST_PRESEEDED_REQUESTERS=120
   LOCUST_RPS_PER_USER=2.05 LOCUST_ENDPOINT=next locust ...`),
   сохранить новые CSV в `tests/load/results/endpoint_next_v2_*.csv`.

---

## 5. Риски и уточнения

- **Risk 1 — Doc decay.** В репозитории несколько слоёв аудита
  (`plan-fix.md`, `audit-round-3.md`, `audit-final.md`,
  `tracking-fix.md`). Если ревьювер откроет старую версию
  `plan-fix.md` (был «как до фиксов»), часть пунктов покажется
  невыполненными. Этот файл теперь обновлён под текущий стейт.
- **Risk 2 — PM-зачёт.** Без явного письменного согласования п.20
  (Locust) и п.21 (notification) ревьювер вправе срезать баллы.
  См. Шаг 3.
- **Risk 3 — Скриншоты «пустые».** Если снять Grafana без живого
  трафика, панели будут серыми / `No data`. Шаг 1 обязательно
  включает прогон Locust + ручные действия в боте *до* съёмки.
- **Risk 4 — Grafana credentials.** В prod-overlay админ-пароль
  берётся из `.env` (`GRAFANA_ADMIN_PASSWORD`). Перед демо нужно
  убедиться, что переменная задана.
- **Уточнить у PM:**
  1. Засчитывается ли Locust как замена JMeter?
  2. Засчитывается ли notification-сервис как доп. этап продукта
     (п.21, до +3 баллов)?
  3. Достаточно ли «локально зелёный CI + скриншот GH Actions run»
     или нужно держать ветку с активным workflow к моменту защиты?

---

## 6. Что НЕ нужно делать

Чтобы не размывать stage4, явно фиксирую — не трогаем:

- Архитектуру (микросервисы / compose) — стабильна.
- Схему БД — соответствует stage1 PRD.
- Бизнес-логику matching / rating — закрыто на stage3.
- Покрытие тестами выше текущих 67 passed — за рамками stage4.
- PgBouncer как отдельный сервис — большой объём, делать только если
  PM явно просит держать 80+ RPS.

---

*Файл обновлён аудитором 2026-05-12 на основе фактического состояния
ветки `stage4`, требований `req.md` и итогов `audit-final.md`.*
