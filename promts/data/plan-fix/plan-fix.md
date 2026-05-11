# План доработки проекта

Источник требований: `promts/requirements/req.md` (система оценивания)
Дата аудита: 2026-05-11
Ветка: `stage4`

## 1. Краткое резюме

ConnectMe — Telegram-бот знакомств, реализованный в виде микросервисной
сборки: `bot` (aiogram 3), `backend` (FastAPI), PostgreSQL, Redis, RabbitMQ,
MinIO, Celery worker+beat, Prometheus + Grafana, nginx-прокси. По 4 этапам
ТЗ закрыты задачи 1–3 (PRD, архитектура, БД, базовый функционал бота, CRUD
анкет, система рейтингов, кэш сессий), а также часть 4-го (Celery beat
`recalculate_all_ratings`, MinIO загрузка фото, RabbitMQ-publisher свайпов
и мэтчей, индексы БД, prod-compose, бэкап-скрипт).

Технологии используются осмысленно: Redis даёт кэш сессий + Sorted Set
рейтинга + дневные счётчики; RabbitMQ — отдельные topic-exchange'ы для
swipe/match/rating/chat; MinIO — реальная загрузка/presigned URL; Celery
beat — ночной пересчёт рейтингов; Prometheus инструментирует FastAPI,
Grafana — дашборд по RPS / p95 / 5xx. Логирование настроено через loguru
с ротацией.

Главные пробелы (по системе оценивания):
- **Нет CI/CD** (нет ни `.github/workflows`, ни `Jenkinsfile`) — теряется
  пункт 7 (до −1 балла).
- **Нет нагрузочного тестирования** Apache JMeter или аналога с отчётом
  (нет ни `.jmx`, ни Locust/k6 артефактов в проекте бота — есть лишь
  учебные `practice/p2/results/*.csv`, никак не привязанные к ConnectMe).
- **RabbitMQ используется только публикацией: нет потребителей** —
  очереди объявляются в `EventPublisher.connect()`, но ни одного consumer
  для `swipe_processing` / `match_notifications` / `rating_calculation` /
  `message_delivery` нет. По критерию «обоснованное применение» это
  снижает балл (фактически события публикуются «в воздух»).
- **Celery task `recalculate_all_ratings` нигде не вызывается явно**, кроме
  beat-расписания, и не используется для разгрузки запросов API (нет
  `.delay()` ни в одном месте кода) — польза ограничена ночным пересчётом.
- **Метрики и логирование**: Prometheus инструментирует только backend; у
  bot и celery_worker метрик нет, RabbitMQ-exporter включён, но ни одной
  бизнес-метрики (свайпы, мэтчи, ошибки matching) в Grafana не выведено —
  дашборд только про HTTP backend.
- **Отчёт по этапу 4 отсутствует** (`docs/stages/stage4_report.md` не
  создан, хотя `tracking_table.md` отмечает этап 4 как закрытый).
- **Конфликт версий Python в проекте**: `practice/p4/.venv` тянет Python
  3.14, корневой `.venv` — 3.11; в Dockerfile-ах нужно проверить.
- **Хардкоженные дефолты секретов** (`change_me_*`) могут утечь, если
  кто-то запустит без `.env`. В `docker-compose.yml` есть default
  публичные dev-default значения — плохая практика.

## 2. Проверенные требования

- [x] **Этап 1 (планирование/проектирование):** `prd.json`,
  `architecture.json`, `database_schema.json`, `dbdiagram.dbml`,
  `docs/stages/stage1_report.md`, `docs/info/architecture.md`,
  `docs/info/database_schema.md`. (0–3 баллов)
- [x] **Этап 2 (базовая функциональность):** бот с FSM на aiogram 3,
  backend FastAPI с CRUD профилей, аутентификация по Telegram ID,
  свайпы/мэтчи, Docker-сборка обоих сервисов. (0–3 баллов)
- [x] **Этап 3 (анкеты + ранжирование):** 17 endpoints, 3-уровневый рейтинг
  (`PrimaryRatingCalculator`, `BehavioralRatingCalculator`,
  `CombinedRatingCalculator`), Redis-кэш 10 анкет на сессию. (0–3 баллов)
- [x] **БД настроена и работает, схема из этапа 1 реализована:** 7
  моделей SQLAlchemy в `backend/models/*.py`, `database/indexes.sql` под
  фактические запросы, init.sql в `infrastructure/postgres/`. (0–3 баллов)
- [x] **Redis (использование):** `ProfileSessionCache` (List + TTL),
  `RatingCache` (Sorted Set), `SwipeCounterCache` (Hash). Использование
  ОБОСНОВАННОЕ, не только Celery-broker → 2 балла.
- [x] **Celery (использование):** настроен worker + beat, задача
  `recalculate_all_ratings` с crontab, Redis как broker/backend.
  Применение узкое (только пересчёт раз в сутки) → реалистично 1 балл из 2.
- [x] **MQ-брокер RabbitMQ:** topic-exchange'ы swipe/match/rating/chat,
  publisher используется в `matching.py` при свайпе и создании мэтча.
  Но **0 потребителей** в коде → применение «полудохлое»; реалистично
  1 балл из 2.
- [x] **S3-хранилище (MinIO):** реальная загрузка через
  `PhotoService.upload_to_storage` + presigned URL + soft-delete фото.
  → 2 балла.
- [x] **Метрики и логирование (частично):** loguru с ротацией для bot и
  backend, Prometheus-instrumentator на FastAPI, Grafana provisioning
  с дашбордом, RabbitMQ Prometheus plugin. Покрытие неполное (нет метрик
  бота/celery/бизнес-метрик), реалистично 1 балл из 2.
- [x] **Бот работает, ручные тесты выдерживает:** `bot_nohup.log`
  фиксирует запуск, `@HUScorp_bot` упоминается как работающий в
  `tracking_table.md`. Подтверждаю «работает», 2–3 балла достижимы.
- [ ] **CI/CD (пункт 7):** ОТСУТСТВУЕТ. Нет `.github/workflows/*`, нет
  `Jenkinsfile`, в скриптах только локальный `deploy.sh`. → 0 баллов.
- [ ] **JMeter / нагрузочное тестирование:** ОТСУТСТВУЕТ для ConnectMe.
  Папка `practice/p2/results/*.csv` относится к учебной практике и не
  привязана к проекту → 0 баллов.
- [ ] **Отчёт по этапу 4:** ОТСУТСТВУЕТ файл `docs/stages/stage4_report.md`,
  хотя `tracking_table.md` отмечает этап как закрытый.
- [ ] **Бизнес-метрики:** не выгружаются ни через `prometheus_client`, ни в
  Grafana-дашборд (только `http_requests_total`, `http_request_duration`).
- [ ] **RabbitMQ-consumer'ы:** не реализованы. Очереди объявляются и
  заполняются, но никто их не читает.
- [?] **Сервис notifications / иной доп. этап:** нет признаков отдельного
  notification-сервиса; уведомления о мэтчах шлются напрямую из бота при
  свайпе, через RabbitMQ не приходят → доп. баллов по «другому этапу» нет.
- [?] **Тесты под нагрузкой DB:** seed-скрипт `scripts/seed_mock_users.py`
  есть, но нет описания, сколько профилей загружено, и нет нагрузочного
  прогона на этих данных.

## 3. Найденные несоответствия

### 3.1 Нет CI/CD
- Требование: пункт 7 системы оценивания — «Настройка CI/CD для бота».
- Текущее состояние: `.github/`, `.gitlab-ci.yml`, `Jenkinsfile`
  отсутствуют. Деплой — ручной через `scripts/deploy.sh`.
- Где обнаружено: корень репозитория.
- Что нужно сделать: добавить `.github/workflows/ci.yml` с минимум двумя
  job'ами — `lint+pytest` (на push/PR) и `build-images` (опционально
  push в GHCR). Можно дополнительно `deploy` на ветку `main` через SSH.
- Приоритет: **высокий** (дешёво, +1 балл).

### 3.2 Нет нагрузочного тестирования (JMeter)
- Требование: «Проведение нагрузочного тестирования с помощью Apache
  JMeter, если в другом формате — обговариваем лично».
- Текущее состояние: нет `.jmx` план-файлов и нет отчёта о прогоне.
  Файлы `practice/p2/results/*.csv` — это учебная практика по
  Redis/RabbitMQ, не нагрузочное тестирование ConnectMe API/бота.
- Где обнаружено: весь репозиторий.
- Что нужно сделать: подготовить JMeter план для критичных
  HTTP-эндпойнтов backend: `POST /api/v1/auth/telegram`,
  `GET /api/v1/matching/next`, `POST /api/v1/matching/swipe`. Сценарий
  — 100–500 виртуальных пользователей, длительность 5–10 мин, отчёт в
  `tests/load/`. Альтернатива (по согласованию) — Locust/k6 c CSV-отчётом.
- Приоритет: **высокий** (+1 балл, и закроет «бот работает под нагрузкой»).

### 3.3 RabbitMQ — нет ни одного consumer
- Требование: «Любое обоснованное применение, использование только для
  работы с Celery расценивается как 1 балл».
- Текущее состояние: `EventPublisher` объявляет 4 очереди с binding'ами,
  публикуется swipe/match. Однако ни в `backend/`, ни в `bot/`,
  ни в `celery_app.py` нет ни одного `consume`/`basic_consume`/`aio_pika`
  receiver'а. События уходят в durable-очереди и копятся.
- Где обнаружено: `infrastructure/rabbitmq/event_publisher.py`,
  `backend/api/v1/matching.py:189`.
- Что нужно сделать: либо
  (а) написать consumer'ы (например, `bot/services/notification_worker.py`
  для `match_notifications` → отправка push'а в Telegram пользователю;
  `rating_calculation` consumer, который дергает `recalculate_for_user`
  Celery-task инкрементально), либо
  (б) подключить как Celery-broker (через `kombu`/`celery+amqp://`) и
  использовать RabbitMQ для очередей Celery — тогда RabbitMQ применяется
  обоснованно.
- Приоритет: **средний** (нужен для полноценного балла за MQ).

### 3.4 Celery используется только для одной ночной задачи
- Требование: «Любое обоснованное применение».
- Текущее состояние: единственная задача — `recalculate_all_ratings`
  по `crontab(hour=3, minute=0)`. Нет `.delay()`/`.apply_async()`
  ни в одном месте API. Тяжёлые операции (загрузка фото в MinIO,
  пересчёт рейтинга после свайпа) делаются синхронно в HTTP-запросе.
- Где обнаружено: `backend/celery_app.py`, `backend/api/v1/*.py`.
- Что нужно сделать: вынести в Celery как минимум:
  (1) пересчёт `behavioral` рейтинга после каждого свайпа (триггерить
  из `_publish_swipe_events`);
  (2) обработку загруженного фото (генерация thumbnail, проверка
  валидности через image processing) — снять с HTTP-горутины;
  (3) отправку push-уведомлений о мэтчах через Telegram (вынести из
  синхронной ветки `swipe_profile`).
- Приоритет: **средний** (+1 балл за Celery).

### 3.5 Метрики неполные
- Требование: «Любое обоснованное применение … запись ошибок в логи без
  полезной информации не засчитывается».
- Текущее состояние: backend имеет HTTP-метрики; bot не инструментирован
  Prometheus'ом совсем; celery_worker — тоже; бизнес-метрик
  (`swipes_total`, `matches_total`, `cache_hit_ratio`,
  `rating_recalc_duration`) нет.
- Где обнаружено: `backend/main.py`, `bot/main.py`, `backend/celery_app.py`,
  `infrastructure/grafana/provisioning/dashboards/connectme.json`.
- Что нужно сделать: добавить `prometheus_client` (Gauge/Counter/Histogram)
  для свайпов, мэтчей, длительности подбора, длительности пересчёта
  рейтинга. В bot — отдельный `/metrics`-сервер на `aiohttp` (на отдельном
  порту, scrape'ить Prometheus'ом). Расширить Grafana-дашборд.
- Приоритет: **средний** (+1 балл по метрикам).

### 3.6 Отчёт по этапу 4 отсутствует
- Требование: внутреннее (этапы продукта 1–4, см. tracking_table).
- Текущее состояние: `docs/stages/` содержит только stage1–3.
- Где обнаружено: `docs/stages/`.
- Что нужно сделать: подготовить `docs/stages/stage4_report.md` по
  фактически закрытым задачам 4.1–4.8 (Celery, MinIO, RabbitMQ events,
  Messages API, DateIdeas, тестирование, prod-deploy).
- Приоритет: низкий (документация).

### 3.7 Дефолтные секреты в `docker-compose.yml`
- Требование: безопасность дефолтной поставки.
- Текущее состояние до фикса: у чувствительных переменных были fallback
  dev-default значения — все эти дефолты
  читаются compose'ом, если в `.env` пусто.
- Где обнаружено: `docker-compose.yml:31-36`, `docker-compose.prod.yml`.
- Что нужно сделать: убрать дефолты у всех чувствительных переменных,
  оставить только `${POSTGRES_PASSWORD:?required}` (compose упадёт без
  переменной). `.env.example` уже есть, README обновить.
- Приоритет: низкий (хорошая практика, без баллов).

### 3.8 Лишние «костыли» инициализации в `lifespan`
- Текущее состояние: `MinIOClient(...)` создаётся ради побочного эффекта
  (создание bucket'а), но переменная не сохраняется — на каждом запросе
  `PhotoService.get_storage_client()` создаёт нового. Это рабочая, но
  ресурсозатратная схема.
- Где обнаружено: `backend/main.py:71-83`, `backend/services/photo_service.py:99`.
- Что нужно сделать: вынести `MinIOClient` в singleton (как `redis_client`),
  переиспользовать. Та же логика для `EventPublisher` — сейчас он
  открывает/закрывает соединение на КАЖДЫЙ свайп
  (`async with EventPublisher(...)`), это TCP-handshake и declare всех
  exchange'ей на каждый запрос. Сделать долгоживущий publisher.
- Приоритет: средний (производительность, влияет на нагрузочные тесты).

### 3.9 `EventPublisher` объявляет очереди при каждом подключении
- Где обнаружено: `infrastructure/rabbitmq/event_publisher.py:67-92`.
- Что нужно сделать: разнести `connect()` на «открыть канал» (горячий
  путь) и `setup_topology()` (один раз при старте приложения). Сейчас
  каждый свайп декларирует 4 exchange + 4 queue + 4 binding.
- Приоритет: средний.

### 3.10 Нет бизнес-логгирования по правилам ТЗ
- Требование: «Запись ошибок в логи без полезной информации не
  засчитывается» — пример: «`Ошибка в модуле matchmaking: не найден
  профиль #1234`».
- Текущее состояние: формат `loguru` хороший, и в `matching.py` ошибки
  логируются с `type(e).__name__`. Но местами есть generic-сообщения
  типа `"⚠️ Redis недоступен"` без контекста. В целом — нормально, но
  стоит пройтись и добавить ID профиля/мэтча/свайпа в WARN/ERROR.
- Приоритет: низкий.

## 4. План фикса

### Шаг 1. CI/CD (GitHub Actions)
Создать `.github/workflows/ci.yml`:
- job `tests`: `python -m pytest tests/ -v` на push в любую ветку и на PR
  в `main`;
- job `docker-build`: matrix `[bot, backend]` — `docker build`, опционально
  `docker push ghcr.io/...` по тэгу `v*`;
- job `lint`: `ruff check backend bot infrastructure`.

### Шаг 2. Нагрузочное тестирование (JMeter)
- Положить план в `tests/load/connectme.jmx` со сценариями для
  `/api/v1/auth/telegram`, `/api/v1/matching/next`, `/api/v1/matching/swipe`.
- Прогон 5 минут × 200 RPS; результаты — `tests/load/results/*.jtl`
  + сводный отчёт в `docs/stages/stage4_loadtest.md` (графики, p95, RPS).
- В README добавить раздел «Нагрузочное тестирование» с командой запуска.

### Шаг 3. RabbitMQ consumer'ы
- `bot/workers/notification_consumer.py`: consume `match_notifications`,
  слать через `bot.send_message` сообщение о мэтче. Запускать как
  отдельный процесс (`docker-compose.prod.yml` сервис `bot_consumer`).
- `backend/workers/rating_consumer.py`: consume `swipe_processing`,
  триггерить `update_behavioral_rating.delay(user_id)` Celery task.

### Шаг 4. Расширить Celery
- `recalculate_user_rating(user_id)` — точечный пересчёт после каждого
  свайпа.
- `process_uploaded_photo(photo_id)` — вынести валидацию/resize.
- `send_match_notification(user_id, match_id)` — заменить синхронную
  отправку из бота.

### Шаг 5. Бизнес-метрики + Grafana
- В backend добавить `prometheus_client.Counter` для
  `swipes_total{action}`, `matches_total`, `Histogram` для
  `matching_session_duration_seconds`, `rating_recalc_duration_seconds`.
- В Grafana дашборд добавить панели: «Свайпы в минуту», «Мэтчи в
  минуту», «Длина очередей RabbitMQ» (через `rabbitmq_queue_messages`).
- Поднять метрики бота на отдельном порту (`aiohttp` `/metrics`),
  добавить scrape-target в `prometheus.yml`.

### Шаг 6. Отчёт по этапу 4
- `docs/stages/stage4_report.md` — структура как в stage1–3:
  выполненные задачи, артефакты, скриншоты дашборда, результаты тестов.

### Шаг 7. Производительность инфраструктуры
- Singleton `EventPublisher` (long-lived connection, declare-once-on-startup).
- Singleton `MinIOClient` (переиспользовать сессию).

### Шаг 8. Безопасность compose
- Убрать дефолтные значения у `POSTGRES_PASSWORD`, `MINIO_*`,
  `RABBITMQ_PASSWORD`, заменить на `${VAR:?required}`.
- Прогнать `gitleaks` / `trufflehog` на репозитории.

## 5. Риски и уточнения

- **Уточнить с преподавателем формат нагрузочного теста**: JMeter обязателен
  или Locust/k6 с отчётом тоже принимаются? В req.md есть оговорка «если в
  другом формате, обговариваем лично».
- **Уточнить, нужны ли доп. этапы (notification-сервис)** для добора баллов
  до 30+ (оценка «5»). Сейчас по факту реализовано: 12 этапов × 3 =
  ориентировочно 12 баллов + Redis (2) + Celery (1) + MQ (1) + S3 (2) +
  метрики (1) + CI/CD (0) ≈ 22 балла. Для 30+ нужен notification-сервис
  и/или вынос на разные машины.
- **`tracking_table.md` декларирует 100% готовности**, но этап 4 не имеет
  собственного отчёта в `docs/stages/` — несоответствие документации
  фактическому состоянию.
- **`bot_nohup.log` (296 KB) и `.venv` лежат в репозитории** — это шум,
  стоит удалить и добавить в `.gitignore` (уже есть `.gitignore`, но,
  судя по статусу, эти артефакты тоже трекаются).
- **Дата сейчас 2026-05-11**, требования из req.md созданы 2026-05-11 (тот же
  день). Подтвердить, что других требований нет.
