# Аналитическая справка по проекту ConnectMe

Дата анализа: 2026-05-03  
Репозиторий: `/home/artwox/orchestrAI/loveBot/projects/connectme`

## 1. Краткое описание

ConnectMe — Telegram dating-бот для пользователей, которые ищут знакомства и испытывают трудности с первым шагом в общении. Продуктовая идея описана в `prd.json`: бот должен помогать создавать анкету, искать подходящие профили, ставить лайки, получать мэтчи, общаться и в перспективе предлагать идеи для свиданий.

Целевая аудитория:

- основные пользователи: люди 18-35 лет, которым сложно начинать знакомство;
- вторичная аудитория: пользователи, ищущие серьёзные отношения через более осознанное и интеллектуальное общение.

Ключевые боли пользователей:

- страх написать первым;
- отсутствие небанальных идей для начала разговора;
- трудности с поддержанием диалога;
- нехватка идей для свиданий.

## 2. Текущее назначение системы

Система строится вокруг Telegram-интерфейса и backend API:

- Telegram Bot принимает команды, ведёт пользователя через FSM-сценарии и обращается к backend.
- Backend API хранит пользователей и анкеты, обрабатывает поиск, свайпы, мэтчи, рейтинг, настройки и фото.
- PostgreSQL является основным хранилищем.
- Redis используется для кэша сессий подбора, рейтингов и счётчиков свайпов.
- RabbitMQ и MinIO подготовлены инфраструктурно, но в основном не интегрированы в пользовательские сценарии backend.

Документация описывает микросервисную целевую архитектуру, однако текущий код фактически ближе к модульному монолиту: один FastAPI-сервис содержит API Gateway, Profile, Matching, Rating и Photo логику.

## 3. Основные пользовательские сценарии

Реализованные или частично реализованные сценарии:

- `/start` — регистрация или авторизация пользователя через Telegram ID.
- `/profile` — просмотр, создание и редактирование анкеты.
- `/search` — просмотр следующей анкеты и свайпы.
- `/matches` — список мэтчей.
- `/rating` — просмотр собственного рейтинга.
- `/settings` — настройка возраста, дистанции, города и предпочтений поиска.
- загрузка, просмотр, удаление и назначение основного фото профиля.

Запланированные, но не полноценно реализованные сценарии:

- real-time чат между мэтчами;
- генерация идей для свиданий;
- полноценная доставка событий через RabbitMQ;
- фоновые задачи Celery для рейтингов, очистки сессий и аналитики;
- фактическая загрузка фото в MinIO;
- Prometheus/Grafana мониторинг.

## 4. Структура проекта

Ключевые директории и файлы:

- `bot/` — Telegram Bot Service на aiogram 3.x.
- `backend/` — FastAPI backend, SQLAlchemy-модели, Pydantic-схемы, бизнес-сервисы.
- `infrastructure/` — конфигурации PostgreSQL, Redis, RabbitMQ, MinIO и helper-клиенты.
- `docs/` — архитектурные документы и отчёты по этапам.
- `tests/` — тесты backend API и stage 3 integration/unit tests с моками.
- `test/` — отдельный набор infrastructure/service tests, требующий живые PostgreSQL/Redis/RabbitMQ.
- `promts/` — роли и инструкции для разработчиков.
- `prd.json` — продуктовые требования.
- `architecture.json` — целевая архитектура и потоки.
- `database_schema.json`, `dbdiagram.dbml`, `infrastructure/postgres/init.sql` — описание и SQL-схема БД.
- `docker-compose.yml` — запуск backend, bot, PostgreSQL, Redis.
- `docker-compose.infra.yml` — отдельный запуск инфраструктуры: PostgreSQL, Redis, RabbitMQ, MinIO.
- `start-all.sh` — локальный запуск backend и bot через `.venv`.

## 5. Backend API

Точка входа: `backend/main.py`.

FastAPI-приложение подключает роутеры:

- `/api/v1/auth/telegram` — регистрация или получение пользователя по Telegram ID.
- `/api/v1/profile` — получение, создание и обновление анкеты.
- `/api/v1/matching/next` — получение следующей анкеты.
- `/api/v1/matching/swipe` — лайк, пропуск или super-like.
- `/api/v1/matching/matches` — список мэтчей.
- `/api/v1/matching/session/refresh` — обновление кэшированной сессии подбора.
- `/api/v1/matching/session/status` — статус Redis-сессии.
- `/api/v1/rating/my` — текущий рейтинг пользователя.
- `/api/v1/settings` — получение и обновление настроек поиска.
- `/api/v1/profile/photo` — загрузка и список фото.
- `/api/v1/profile/photo/{photo_id}` — удаление фото.
- `/api/v1/profile/photo/{photo_id}/set-primary` — назначение основного фото.
- `/api/v1/health` — health check API, Redis и БД.

Основные backend-сервисы:

- `ProfileService` — пользователи, анкеты, свайпы, мэтчи.
- `MatchingService` — подбор 10 анкет, фильтрация, ранжирование по рейтингу, Redis-кэш.
- `RatingService` — расчёт первичного, поведенческого и комбинированного рейтингов.
- `PhotoService` — валидация фото, лимит 6 фото, запись метаданных, soft delete, primary photo.

## 6. Telegram Bot

Точка входа: `bot/main.py`.

Технологии:

- aiogram 3.x;
- MemoryStorage для FSM;
- httpx-клиент для backend API;
- middleware авторизации через backend;
- поддержка HTTP/HTTPS proxy для Telegram API.

Ключевые модули:

- `bot/api_client.py` — HTTP-клиент к backend.
- `bot/middlewares/auth.py` — авто-регистрация пользователя при обновлениях Telegram.
- `bot/handlers/start.py` — `/start`, onboarding, переход к созданию профиля.
- `bot/handlers/profile.py` — FSM создания и редактирования анкеты.
- `bot/handlers/search.py` — поиск анкет, swipe like/pass, хранение текущей анкеты в FSM.
- `bot/handlers/matches.py` — список мэтчей.
- `bot/handlers/rating.py` — вывод рейтинга.
- `bot/handlers/settings.py` — настройки поиска.
- `bot/handlers/photos.py` — загрузка и управление фото.
- `bot/handlers/common.py` — `/cancel`, заглушки чата и идей для свиданий.
- `bot/keyboards/inline.py` — inline-клавиатуры.
- `bot/states.py` — FSM-состояния для профиля и поиска.

В проекте также есть `bot/simple_bot.py` и `bot/test_bot.py` — упрощённые версии для проверки Telegram API и запуска без backend.

## 7. Модель данных

Основная БД: PostgreSQL 15+.

Текущие SQLAlchemy-модели:

- `users` — Telegram-пользователь, бан, активность, soft delete.
- `profiles` — анкета, возрастные настройки, пол, интересы, город, гео, верификация.
- `photos` — метаданные фото, primary flag, soft delete, moderation status.
- `swipes` — история лайков, пропусков и super-like.
- `matches` — взаимные лайки, статус, счётчик сообщений, последние сообщения.
- `messages` — модель сообщений чата присутствует, но chat API не реализован.
- `ratings_combined` — комбинированный рейтинг профиля.

SQL-схема в `infrastructure/postgres/init.sql` шире текущих моделей и включает также:

- `ratings_primary`;
- `ratings_behavioral`;
- `sessions`;
- дополнительные сущности из `database_schema.json`, включая жалобы, блокировки, date ideas, audit/events/metrics.

Важное расхождение: целевая схема требует `profiles.date_of_birth` и `profiles.gender` как `NOT NULL`, но SQLAlchemy-модель допускает `None`, а создание профиля через API может передавать неполные данные. Это потенциальная зона ошибки при работе с реальной PostgreSQL-схемой.

## 8. Рейтинг и matching

Рейтинг состоит из трёх уровней:

- первичный рейтинг: заполненность анкеты, фото, верификация;
- поведенческий рейтинг: лайки, пропуски, мэтчи, сообщения, активность;
- комбинированный рейтинг: взвешенная сумма primary, behavioral и referral bonus.

В коде веса комбинированного рейтинга:

- `PRIMARY_WEIGHT = 0.40`;
- `BEHAVIORAL_WEIGHT = 0.50`;
- `REFERRAL_WEIGHT = 0.10`.

Matching:

- исключает текущий профиль;
- исключает уже свайпнутые анкеты;
- фильтрует по активности;
- применяет предпочтения пользователя;
- сортирует по `ratings_combined.total_score`;
- кэширует до 10 анкет в Redis на 1 час.

Redis-ключи:

- `ranked_profiles:{user_id}:{session_id}` — список анкет для swipe-сессии;
- `ratings:{type}` — sorted set рейтингов;
- `swipes:daily:{user_id}:{date}` — дневные счётчики свайпов.

## 9. Инфраструктура

`docker-compose.yml` запускает:

- `bot`;
- `backend`;
- `db` на PostgreSQL 15 Alpine;
- `redis` на Redis 7 Alpine.

`docker-compose.infra.yml` запускает расширенную инфраструктуру:

- PostgreSQL с `infrastructure/postgres/init.sql` и `postgresql.conf`;
- Redis с `infrastructure/redis/redis.conf`;
- RabbitMQ Management на портах `5672` и `15672`;
- MinIO на портах `9000` и `9001`.

Инфраструктурные helper-модули:

- `infrastructure/redis/cache_patterns.py` — кэш анкет, рейтингов и свайпов.
- `infrastructure/rabbitmq/event_publisher.py` — publisher для `swipe_events`, `match_events`, `rating_updates`, `chat_messages`.
- `infrastructure/minio/minio_client.py` — загрузка, presigned URL и удаление фото.

## 10. Текущее состояние реализации

Готово или близко к готовому:

- базовый FastAPI backend;
- Telegram bot с основными командами;
- middleware авторизации через Telegram ID;
- CRUD анкеты;
- поиск следующей анкеты;
- запись свайпов и создание мэтча при взаимном лайке;
- список мэтчей;
- настройки поиска;
- расчёт рейтингов в сервисном слое;
- Redis cache patterns;
- RabbitMQ publisher как отдельная утилита;
- MinIO client как отдельная утилита;
- Docker Compose для базового запуска и отдельной инфраструктуры;
- набор unit/integration tests.

Частично реализовано:

- фото: backend валидирует и пишет metadata в БД, но фактическая загрузка в MinIO отмечена как TODO;
- RabbitMQ: publisher есть, но matching endpoint пока не публикует события;
- Redis: matching использует кэш с fallback, но счётчики свайпов и rating cache применяются не во всех сценариях;
- рейтинг: алгоритмы есть, сохранение и фоновые пересчёты требуют доработки;
- чат: модель сообщений есть, но API и bot-сценарий чата отсутствуют;
- мониторинг: описан в README/архитектуре, но конфигурации Prometheus/Grafana в дереве проекта не обнаружены.

Не реализовано или является заглушкой:

- Celery worker и Celery Beat;
- WebSocket chat service;
- полноценная media pipeline с MinIO;
- модерация фото;
- идеи для свиданий;
- event-driven обработка swipe/match/rating/chat событий;
- production-grade auth/JWT;
- rate limiting.

## 11. Тестирование

Тестовые наборы:

- `tests/test_api_endpoints.py` — smoke/integration проверки API, часть тестов допускает `500` без мокированной БД.
- `tests/test_stage3_integration.py` — unit/integration проверки rating, matching, Redis patterns, photo validation на моках.
- `test/services/test_rating_service.py` — unit-тесты рейтинга.
- `test/redis/test_redis_cache.py` — тесты Redis cache patterns, требуют Redis.
- `test/rabbitmq/test_rabbitmq_publisher.py` — тесты RabbitMQ publisher, требуют RabbitMQ.
- `test/infrastructure/test_health_check.py` — проверки доступности Redis, PostgreSQL, RabbitMQ.

Скрипт `scripts/run-tests.sh` запускает тесты из директории `test/`, а не из `tests/`. Это важно: в проекте есть две параллельные директории тестов, и они покрывают разные уровни.

## 12. Риски и несоответствия

Ключевые риски:

- Целевая архитектура в документации шире текущей реализации. В roadmap нужно явно разделять "описано" и "работает в коде".
- Есть расхождения между SQL-схемой и SQLAlchemy-моделями, особенно по nullable-полям профиля и таблицам рейтингов.
- `ratings_combined.tier` в SQLAlchemy-модели задан как `SmallInteger`, хотя схема БД и API ожидают строковые tier значения `S/A/B/C/D/E`.
- В `docker-compose.yml` backend зависит только от PostgreSQL и Redis; RabbitMQ и MinIO не входят в основной compose, хотя переменные окружения для них заданы.
- Фото сохраняется только как metadata: пользовательский сценарий загрузки выглядит успешным, но объект в S3 фактически не появляется.
- Чат и идеи для свиданий отображаются в интерфейсе как доступные кнопки, но обработчики являются заглушками.
- Health check может возвращать degraded при недоступных Redis/DB, но API продолжает стартовать без БД/Redis; это полезно для локального запуска, но требует явной политики для production.
- Тесты частично проверяют наличие классов и happy path на моках; end-to-end покрытие пользовательских сценариев пока ограничено.

## 13. Рекомендуемые ближайшие шаги

1. Синхронизировать SQLAlchemy-модели, `init.sql` и Pydantic-схемы.
2. Исправить тип `RatingCombined.tier` на строковый и проверить сохранение рейтинга.
3. Подключить фактическую загрузку и удаление фото через `MinIOClient`.
4. Интегрировать `EventPublisher` в matching/photo/rating сценарии.
5. Добавить Celery worker для пересчёта рейтингов и очистки Redis-сессий.
6. Развести тесты `test/` и `tests/` или унифицировать запуск, чтобы CI не пропускал часть покрытия.
7. Реализовать минимальный chat API и Telegram-сценарий сообщений между мэтчами.
8. Добавить миграции Alembic вместо ручной поддержки `init.sql`.
9. Добавить явный `.env.example`, если он ожидается README, но отсутствует в репозитории.
10. Обновить README: ссылки на `stage1_report.md`, `database_schema.md` и `dbdiagram.dbml` сейчас указаны без фактических путей `docs/stages/`, `docs/info/`.

## 14. Вывод

ConnectMe уже имеет рабочий каркас продукта: Telegram bot, FastAPI backend, базовые сущности знакомств, matching, рейтинги, Redis-паттерны и инфраструктурные заготовки. Главная особенность текущего состояния — проект находится между архитектурным прототипом и полноценной интегрированной системой. Для следующего этапа критично не расширять список новых функций, а довести сквозные сценарии до конца: анкета, фото, поиск, свайп, мэтч, сообщение, рейтинг и события.
