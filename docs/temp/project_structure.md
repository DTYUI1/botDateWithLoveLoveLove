# ConnectMe — Структура проекта

> **Дата актуализации:** 10 апреля 2026 г.
> **Версия:** 1.1.0
> **Тип:** Dating-бот в Telegram с микросервисной архитектурой
> **Ветка:** `stage1` (опережает origin/stage1 на 2 коммита)

---

## 📋 Оглавление

1. [Общее описание](#общее-описание)
2. [Корневая структура](#корневая-структура)
3. [Backend (FastAPI)](#backend-fastapi)
4. [Bot (aiogram 3.x)](#bot-aiogram-3x)
5. [Инфраструктура](#инфраструктура)
6. [Тесты](#тесты)
7. [Скрипты](#скрипты)
8. [Документация](#документация)
9. [Промпты для разработки](#промты-для-разработки)
10. [Технологический стек](#технологический-стек)
11. [Архитектурные решения](#архитектурные-решения)
12. [Текущий статус](#текущий-статус)

---

## Общее описание

**ConnectMe** — это умный dating-бот для Telegram, который помогает пользователям 18-35 лет находить серьёзные отношения. Бот не только подбирает пары по интересам и рейтингу, но и предоставляет удобный интерфейс для общения.

### Ключевые возможности
- Регистрация и создание детальных анкет
- Поиск и свайп анкет (лайк/пропуск)
- Система мэтчей при взаимных лайках
- Чат с мэтчами (модель сообщений готова, API не реализовано)
- Многоуровневая система рейтингов (Primary → Behavioral → Combined)
- Кэширование анкет в Redis (10 анкет на сессию)
- Настройки поиска (возраст, расстояние, ориентация)
- Загрузка и управление фотографиями (до 6 фото, валидация формата/размера)

---

## Корневая структура

```
connectme/
├── .env.example              # Шаблон переменных окружения
├── .gitignore                # Исключения для Git
├── .dockerignore             # Исключения для Docker
├── architecture.json         # Полная архитектурная спецификация
├── database_schema.json      # Схема базы данных (PostgreSQL)
├── dbdiagram.dbml            # DBML для визуализации схемы (dbdiagram.io)
├── docker-compose.yml        # Полный Docker Compose (все сервисы)
├── docker-compose.infra.yml  # Только инфраструктура (DB, Redis, RabbitMQ, MinIO)
├── prd.json                  # Product Requirements Document
├── README.md                 # Краткое руководство
├── start-all.sh              # Скрипт локального запуска (backend + bot)
├── tracking_table.md         # Трекинг задач по этапам
│
├── backend/                  # Backend API (FastAPI)
├── bot/                      # Telegram Bot (aiogram 3.x)
├── docs/                     # Документация проекта
│   ├── info/                 # Справочная информация
│   └── stages/               # Отчёты по этапам разработки
├── infrastructure/           # Конфигурация инфраструктуры
│   ├── postgres/             # PostgreSQL конфиг, init.sql, миграции
│   ├── redis/                # Redis конфиг, паттерны кэширования
│   ├── rabbitmq/             # RabbitMQ конфиг, определения очередей
│   └── minio/                # MinIO скрипты и клиент
├── logs/                     # Логи приложения (git-ignored)
├── promts/                   # Промпты для AI-ассистентов
├── scripts/                  # Скрипты автоматизации
├── test/                     # Тесты (unit + infrastructure)
└── tests/                    # Интеграционные тесты API
```

---

## Backend (FastAPI)

**Путь:** `backend/`
**Технологии:** FastAPI, SQLAlchemy 2.x, asyncpg, Pydantic v2
**Порт:** 8005 (локально) / 8000 (в Docker)
**Swagger:** http://localhost:8005/docs

### Структура

```
backend/
├── __init__.py
├── main.py                   # Точка входа: FastAPI app, lifespan (DB + Redis init), 7 роутеров
├── Dockerfile                # Python 3.11-slim, uvicorn port 8000
├── .dockerignore
├── requirements.txt          # Все зависимости + celery, aio-pika, minio, prometheus-client
│
├── api/                      # API роутеры
│   ├── __init__.py
│   └── v1/
│       ├── __init__.py
│       ├── auth.py           # POST /auth/telegram — аутентификация по Telegram ID
│       ├── profile.py        # GET/POST/PUT /profile — CRUD профилей
│       ├── matching.py       # GET/POST /matching/* — свайпы, подбор, сессии, мэтчи
│       ├── rating.py         # GET /rating/my — комбинированный рейтинг
│       ├── settings.py       # GET/PUT /settings — настройки поиска
│       ├── photos.py         # CRUD /profile/photo — загрузка, удаление, primary
│       └── health.py         # GET /health — проверка API + Redis + DB
│
├── core/                     # Базовая конфигурация
│   ├── __init__.py
│   ├── config.py             # BackendSettings (pydantic-settings, env vars)
│   ├── database.py           # Async SQLAlchemy engine, session factory, init_db()
│   └── redis_client.py       # RedisClient singleton (connect, disconnect, health, factories)
│
├── models/                   # SQLAlchemy модели (8 файлов)
│   ├── __init__.py
│   ├── user.py               # users — UUID, telegram_id (unique), username, is_banned, ...
│   ├── profile.py            # profiles — user_id (FK, unique), gender, bio, interests (JSONB), ...
│   ├── photo.py              # photos — profile_id (FK), s3_key, moderation_status, soft delete
│   ├── swipe.py              # swipes — swiper_id, swiped_id, action (enum), source, context_data
│   ├── match.py              # matches — profile1_id, profile2_id, status, last_message_preview
│   ├── message.py            # messages — match_id, sender_id, content, media_urls (JSONB), is_read
│   └── rating.py             # ratings_combined — profile_id, scores, tier, percentile, rank
│
├── schemas/                  # Pydantic v2 схемы (6 файлов)
│   ├── __init__.py
│   ├── user.py               # UserBase, UserCreate, UserResponse
│   ├── profile.py            # ProfileBase, ProfileCreate, ProfileUpdate, ProfileResponse, ProfileShort
│   ├── match.py              # SwipeRequest, SwipeResponse, MatchResponse
│   ├── rating.py             # RatingResponse
│   └── settings.py           # SettingsResponse, SettingsUpdate
│
└── services/                 # Бизнес-логика (5 файлов)
    ├── __init__.py
    ├── profile_service.py    # ProfileService — CRUD users/profiles, swipe, match, helpers
    ├── matching_service.py   # MatchingService — подбор 10 анкет, фильтрация, Redis cache
    ├── rating_service.py     # RatingService + 3 калькулятора (Primary, Behavioral, Combined)
    └── photo_service.py      # PhotoService — валидация, CRUD фото, MinIO (TODO)
```

### Основные эндпоинты API (17 endpoints)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/v1/auth/telegram` | Аутентификация/создание пользователя по Telegram ID |
| GET | `/api/v1/profile?telegram_id={id}` | Получить профиль (null если нет) |
| POST | `/api/v1/profile?telegram_id={id}` | Создать профиль |
| PUT | `/api/v1/profile?telegram_id={id}` | Обновить профиль |
| POST | `/api/v1/profile/photo` | Загрузить фото (multipart/form-data, макс 6, JPEG/PNG/WebP/GIF, до 10МБ) |
| GET | `/api/v1/profile/photo` | Получить все фото профиля |
| DELETE | `/api/v1/profile/photo/{photo_id}` | Удалить фото (soft delete) |
| POST | `/api/v1/profile/photo/{photo_id}/set-primary` | Назначить основное фото |
| GET | `/api/v1/matching/next` | Следующая анкета для свайпа (Redis → MatchingService → ProfileService fallback) |
| POST | `/api/v1/matching/swipe` | Лайк/пропуск/суперлайк с автопроверкой мэтча |
| GET | `/api/v1/matching/matches` | Список мэтчей пользователя |
| POST | `/api/v1/matching/session/refresh` | Обновить сессию подбора |
| GET | `/api/v1/matching/session/status` | Статус сессии кэша |
| GET | `/api/v1/rating/my` | Получить рейтинг (tier, percentile, scores) |
| GET | `/api/v1/settings` | Получить настройки поиска |
| PUT | `/api/v1/settings` | Обновить настройки (возраст, расстояние, ориентация) |
| GET | `/api/v1/health` | Health check (API + Redis + DB) |

---

## Bot (aiogram 3.x)

**Путь:** `bot/`
**Технологии:** aiogram 3.x, aiohttp, httpx
**Прокси:** `http://127.0.0.1:7897` (Koala Clash) / `http://host.docker.internal:7897` (Docker)

### Структура

```
bot/
├── __init__.py
├── main.py                   # Точка входа: Bot, Dispatcher, AuthMiddleware, 6 handlers
├── simple_bot.py             # Минимальный бот (для тестов, без backend)
├── test_bot.py               # Тестовый бот
├── api_client.py             # HTTP-клиент (httpx) для Backend API (10 методов)
├── config.py                 # BotSettings (telegram_bot_token, backend_url, log_level)
├── states.py                 # FSM состояния для диалогов
├── Dockerfile
├── requirements.txt
│
├── handlers/                 # Обработчики команд (6 файлов)
│   ├── __init__.py
│   ├── start.py              # /start — регистрация
│   ├── profile.py            # /profile — создание/редактирование анкеты
│   ├── search.py             # /search — поиск анкет
│   ├── matches.py            # /matches — список мэтчей
│   ├── rating.py             # /rating — мой рейтинг
│   └── settings.py           # /settings — настройки поиска
│
├── middlewares/              # Middleware
│   ├── __init__.py
│   └── auth.py               # AuthMiddleware — авторизация через backend
│
├── keyboards/                # Inline-клавиатуры
│   ├── __init__.py
│   └── inline.py             # Кнопки: ❤️ Лайк, ❌ Пропустить, и т.д.
│
└── logs/                     # Логи бота (git-ignored)
```

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начать работу с ботом, регистрация |
| `/profile` | Просмотр и редактирование своего профиля |
| `/search` | Начать поиск анкет для лайков |
| `/matches` | Просмотр списка мэтчей |
| `/rating` | Узнать свой рейтинг |
| `/settings` | Настройки предпочтений и поиска |

### APIClient методы (bot/api_client.py)

| Метод | Backend Endpoint |
|-------|-----------------|
| `get_or_create_user()` | `POST /auth/telegram` |
| `get_profile()` | `GET /profile` |
| `create_profile()` | `POST /profile` |
| `update_profile()` | `PUT /profile` |
| `get_next_profile()` | `GET /matching/next` |
| `swipe()` | `POST /matching/swipe` |
| `get_matches()` | `GET /matching/matches` |
| `get_rating()` | `GET /rating/my` |
| `get_settings()` | `GET /settings` |
| `update_settings()` | `PUT /settings` |

---

## Инфраструктура

### Docker Compose сервисы

#### 1. PostgreSQL (`db`)
- **Образ:** `postgres:15-alpine`
- **Порт:** 5432
- **Конфиг:** `infrastructure/postgres/postgresql.conf` (shared_buffers=256MB, SSD оптимизация)
- **Init:** `infrastructure/postgres/init.sql` (полная схема БД)
- **Миграции:** `infrastructure/postgres/migrations/` (папка для Alembic)
- **Таблицы:** users, profiles, photos, swipes, matches, messages, ratings_combined
- **Enums:** gender_enum, looking_for_enum, swipe_action_enum, match_status_enum, moderation_status_enum

#### 2. Redis (`redis`)
- **Образ:** `redis:7-alpine`
- **Порт:** 6379
- **Конфиг:** `infrastructure/redis/redis.conf` (maxmemory=512MB, allkeys-lru, AOF)
- **Назначение:**
  - Кэширование анкет (`ranked_profiles:{user_id}:{session_id}`, List, TTL 3600s)
  - Кэширование рейтингов (`ratings:{type}`, Sorted Set)
  - Счётчики свайпов (`swipes:daily:{user_id}:{date}`, Hash)
- **Паттерны:** `infrastructure/redis/cache_patterns.py` (ProfileSessionCache, RatingCache, SwipeCounterCache)

#### 3. RabbitMQ (`rabbitmq`)
- **Образ:** `rabbitmq:3-management-alpine`
- **Порты:** 5672 (AMQP), 15672 (Management UI)
- **Конфиг:** `infrastructure/rabbitmq/rabbitmq.conf` + `definitions.json`
- **Exchanges:** swipe_events, match_events, rating_updates, chat_messages (topic)
- **Queues:** swipe_processing, match_notifications, rating_calculation, message_delivery
- **Publisher:** `infrastructure/rabbitmq/event_publisher.py`

#### 4. MinIO (`minio`)
- **Образ:** `minio/minio:latest`
- **Порты:** 9000 (API), 9001 (Console)
- **Bucket:** `profile-photos` (private)
- **Скрипт:** `infrastructure/minio/setup.sh`
- **Клиент:** `infrastructure/minio/minio_client.py` (upload, presigned URL, delete)

### Конфигурация инфраструктуры

```
infrastructure/
├── README.md                 # Полная документация инфраструктуры
├── STAGE3_SETUP.md           # Отчёт о подготовке для Этапа 3
├── VERIFICATION_REPORT.md    # Отчёт верификации
│
├── postgres/
│   ├── postgresql.conf       # Оптимизированный конфиг PostgreSQL
│   ├── init.sql              # Полная схема БД + индексы + триггеры
│   └── migrations/           # Папка для миграций Alembic
│
├── redis/
│   ├── redis.conf            # Оптимизированный конфиг Redis
│   └── cache_patterns.py     # Паттерны кэширования (3 класса)
│
├── rabbitmq/
│   ├── rabbitmq.conf         # Конфиг RabbitMQ
│   ├── definitions.json      # Exchanges, queues, bindings
│   └── event_publisher.py    # Python publisher событий
│
└── minio/
    ├── setup.sh              # Скрипт создания bucket'ов
    └── minio_client.py       # Python клиент для MinIO
```

---

## Тесты

### Unit-тесты (`test/`)

```
test/
├── __init__.py
├── pytest.ini
├── requirements.txt
├── README.md
│
├── infrastructure/
│   ├── __init__.py
│   └── test_health_check.py        # 5 тестов (PostgreSQL, Redis, RabbitMQ, MinIO)
│
├── services/
│   ├── __init__.py
│   └── test_rating_service.py      # 24 теста (Primary: 7, Behavioral: 9, Combined: 8)
│
├── redis/
│   ├── __init__.py
│   └── test_redis_cache.py         # 8 тестов (SessionCache: 3, RatingCache: 3, SwipeCounter: 2)
│
└── rabbitmq/
    ├── __init__.py
    └── test_rabbitmq_publisher.py  # 6 тестов (подключение + 4 типа событий)
```

**Результат:** ✅ 24/24 unit tests passed (rating_service)

### Интеграционные тесты API (`tests/`)

```
tests/
├── conftest.py
├── pytest.ini
├── requirements.txt
├── test_api_endpoints.py           # 12 тестов (11/12, 1 интеграционный требует БД)
└── test_stage3_integration.py      # 29 тестов (29/29, 100%)
```

**Тестовое покрытие:**
- PrimaryRatingCalculator: 6/6 ✅
- BehavioralRatingCalculator: 9/9 ✅
- CombinedRatingCalculator: 4/4 ✅
- PhotoService: 5/5 ✅
- MatchingService: 2/2 ✅
- RedisCachePatterns: 3/3 ✅

---

## Скрипты

**Путь:** `scripts/`

| Скрипт | Описание |
|--------|----------|
| `setup-infra.sh` | Полная установка инфраструктуры (Docker check → .env → запуск → health check → MinIO setup) |
| `health-check.sh` | Проверка здоровья всех сервисов (контейнеры, PostgreSQL, Redis, RabbitMQ, MinIO, Backend API) |
| `run-tests.sh` | Запуск всех тестов через pytest с установкой зависимостей |

---

## Документация

### `docs/info/` — Справочная информация

### `docs/stages/` — Отчёты по этапам
| Файл | Описание |
|------|----------|
| `stage1_report.md` | Отчёт по Этапу 1 (планирование) |
| `stage2_report.md` | Отчёт по Этапу 2 (разработка) |

### `docs/temp/` — Временные файлы
| Файл | Описание |
|------|----------|
| `project_structure.md` | Данный файл — структура проекта |
| `BACKEND_STATUS.md` | Статус готовности Backend API |

### Корневые JSON-документы
| Файл | Описание |
|------|----------|
| `architecture.json` | Полная архитектурная спецификация (сервисы, диаграммы, API, data flow, метрики) |
| `database_schema.json` | Детальная схема БД (таблицы, колонки, индексы, FK, enum-ы) |
| `prd.json` | Product Requirements Document (требования, user stories, критерии успеха) |

---

## Промпты для разработки

**Путь:** `promts/`

| Файл | Описание |
|------|----------|
| `backend_developer.md` | Промпт для AI-ассистента: Backend Developer (FastAPI, SQLAlchemy, сервисы) |
| `telegram_bot_developer.md` | Промпт для AI-ассистента: Telegram Bot Developer (aiogram, handlers, keyboards) |
| `queue_cache_engineer.md` | Промпт для AI-ассистента: Queue/Cache Engineer (Redis, RabbitMQ, Celery) |

---

## Технологический стек

### Backend
- **FastAPI** — асинхронный веб-фреймворк
- **SQLAlchemy 2.x** — ORM (DeclarativeBase, async engine)
- **asyncpg** — асинхронный драйвер PostgreSQL
- **Pydantic v2** — валидация данных (ConfigDict, from_attributes)
- **Uvicorn** — ASGI сервер
- **Alembic** — миграции (в requirements, не используется)

### Bot
- **aiogram 3.x** — асинхронный фреймворк для Telegram Bot API
- **aiohttp** — HTTP-клиент с поддержкой прокси (AiohttpSession)
- **httpx** — HTTP-клиент для Backend API (trust_env=False)
- **FSM** — машина состояний для диалогов

### Инфраструктура
- **PostgreSQL 15** — реляционная БД (PostGIS, JSONB, индексы, триггеры)
- **Redis 7** — кэш, счётчики, сессии (maxmemory 512MB, allkeys-lru, AOF)
- **RabbitMQ 3.12** — очередь сообщений (topic exchanges, definitions.json)
- **MinIO** — S3-совместимое хранилище (bucket: profile-photos, private)
- **Docker & Docker Compose** — контейнеризация

### В requirements, но не реализовано
- **Celery 5.x** — фоновые задачи (пересчёт рейтингов, очистка сессий)
- **aio-pika** — асинхронный AMQP клиент для RabbitMQ
- **prometheus-client** — метрики мониторинга
- **minio** — официальный Python SDK для MinIO

---

## Архитектурные решения

### Монолитная архитектура Backend (фактическая)

Несмотря на описание в `architecture.json` 5 отдельных микросервисов, фактически весь backend реализован как **единое FastAPI-приложение** на порту 8000 (Docker) / 8005 (локально):

```
┌─────────────┐
│   Telegram   │
│   Client     │
└──────┬──────┘
       │ commands, messages
       ▼
┌─────────────────────────┐
│  Telegram Bot Service   │  ← aiogram 3.x + httpx APIClient
│  (6 handlers, middleware)│
└──────┬──────────────────┘
       │ REST API (httpx)
       ▼
┌─────────────────────────┐
│    Backend API          │  ← FastAPI (единое приложение)
│  (7 роутеров, 17 endpoints)│
├─────────────────────────┤
│  Auth │ Profile │ Match│
│  Rating │ Settings │   │
│  Photos │ Health │     │
└──────┬──────────────────┘
       │
       ├──────────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│PostgreSQL│  │  Redis   │  │ RabbitMQ │  │  MinIO   │
│  (7 табл)│  │ (кэш)    │  │(events)  │  │ (фото)   │
└──────────┘  └──────────┘  └──────────┘  └──────────┘
```

### Система рейтингов

Многоуровневая система ранжирования пользователей:

1. **Primary Rating** (on_profile_update)
   - Полнота анкеты (10 факторов с весами)
   - Качество фото (количество + главное фото)
   - Бонус верификации (+5%)
   - Формула: `completeness * 0.60 + photo_quality * 0.40 + verification_bonus`

2. **Behavioral Rating** (daily, через Celery — не реализовано)
   - Полученные лайки (логарифмическая шкала)
   - Соотношение лайков/пропусков
   - Частота мэтчей
   - Инициирование диалогов
   - Паттерн активности (longevity + recency)

3. **Combined Rating** (daily)
   - Формула: `primary * 0.40 + behavioral * 0.50 + referral_bonus * 0.10`
   - Тиры: S (0.90+), A (0.75+), B (0.60+), C (0.45+), D (0.30+), E (<0.30)
   - Перцентиль и позиция в рейтинге

### Кэширование анкет

- При начале сессии загружается 10 анкет в Redis
- Ключ: `ranked_profiles:{user_id}:{session_id}`
- Тип: List, TTL: 3600 секунд
- Обновление: при завершении сессии или явном refresh
- Ранжирование: по комбинированному рейтингу

### Data Flow примеры

1. **Регистрация:** Telegram → Bot → POST /auth/telegram → PostgreSQL (users) → Bot
2. **Создание анкеты:** Telegram → Bot (FSM) → POST /profile → PostgreSQL (profiles) → Bot
3. **Подбор анкет:** Telegram → /search → Bot → GET /matching/next → Redis cache → PostgreSQL (miss) → MatchingService → Redis (cache 10) → Bot → Telegram
4. **Лайк:** Telegram → Bot → POST /matching/swipe → PostgreSQL (swipes) → автопроверка мэтча → PostgreSQL (matches) → Bot → Telegram
5. **Рейтинг:** Telegram → /rating → Bot → GET /rating/my → Redis cache → PostgreSQL → Bot → Telegram

---

## Текущий статус

### ✅ Реализовано и работает
- **Infrastructure:** PostgreSQL, Redis, RabbitMQ, MinIO (Docker Compose, конфиги, health checks)
- **Backend API:** FastAPI приложение, **17/17 endpoints → 200 OK**
  - Auth, Profile CRUD, Photos CRUD, Matching (свайпы, мэтчи, сессии), Rating, Settings, Health
- **Bot:** aiogram 3.x, AuthMiddleware, 6 handlers, APIClient (10 методов)
- **Rating Service:** 3 уровня калькуляторов (Primary, Behavioral, Combined)
- **Matching Service:** Подбор 10 анкет, фильтрация, Redis кэш
- **Photo Service:** Валидация upload, CRUD фото (MinIO интеграция — TODO)
- **Тесты:** 24/24 unit + 29/29 integration + 11/12 API
- **Скрипты:** setup-infra.sh, health-check.sh, run-tests.sh

### ⚠️ Частично реализовано
- **MinIO интеграция:** Эндпоинты фото работают (валидация + БД), но загрузка в MinIO — заглушка
- **RabbitMQ события:** Эндпоинты готовы, но публикация в exchanges — TODO
- **Redis кэш matching:** MatchingService поддерживает кэш, fallback на ProfileService если Redis недоступен

### 📝 Не реализовано (запланировано)
| Функция | Описание | Приоритет |
|---------|----------|-----------|
| **MinIO upload** | Загрузка фото в S3, presigned URLs | 🔴 Высокий |
| **RabbitMQ publisher** | Публикация swipe/match событий | 🟡 Средний |
| **Celery worker** | Фоновый пересчёт behavioural рейтинга, очистка сессий | 🟡 Средний |
| **Messages API** | GET/POST `/api/v1/messages/{match_id}` для real-time чата | 🟡 Средний |
| **WebSocket чат** | Real-time сообщения между мэтчами | 🟢 Низкий |
| **Rate limiting** | Ограничение свайпов/запросов | 🟢 Низкий |
| **Alembic миграции** | Вместо create_all() | 🟢 Низкий |
| **Prometheus метрики** | Мониторинг и визуализация | 🟢 Низкий |

### 🔑 Известные проблемы и решения
1. **Прокси для Telegram:** `AiohttpSession(proxy="http://127.0.0.1:7897")` / `http://host.docker.internal:7897`
2. **HTTP_PROXY для httpx:** `trust_env=False` + `os.environ.pop()` в `api_client.py`
3. **ForeignKey:** Добавлен `ForeignKey("profiles.id")` в `models/photo.py`
4. **Pydantic v2:** `model_config = ConfigDict(from_attributes=True)` во всех схемах
5. **ProfileResponse:** Переписан без наследования от ProfileBase для избежания конфликта валидации
6. **Bot URL мэтчей:** Исправлен с `/api/v1/matches` на `/api/v1/matching/matches`

---

## Быстрый старт

### 1. Инфраструктура
```bash
./scripts/setup-infra.sh
```

### 2. Проверка здоровья
```bash
./scripts/health-check.sh
```

### 3. Backend
```bash
cd backend
DATABASE_URL="postgresql+asyncpg://connectme_user:connectme_secure_pass@127.0.0.1:5432/connectme_db" \
REDIS_URL="redis://127.0.0.1:6379/0" \
RABBITMQ_URL="amqp://guest:guest@127.0.0.1:5672//" \
../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8005
```

### 4. Bot (с прокси)
```bash
PYTHONPATH=. HTTP_PROXY="http://127.0.0.1:7897" HTTPS_PROXY="http://127.0.0.1:7897" \
.venv/bin/python bot/main.py
```

### 5. Тесты
```bash
# Unit-тесты
cd test && pytest -v

# Интеграционные тесты
cd tests && pytest -v

# Все тесты
./scripts/run-tests.sh
```

### Или всё сразу
```bash
./start-all.sh
```

---

## Git-статус

- **Ветка:** `stage1`
- **Опережает origin/stage1 на 2 коммита**
- **Последний коммит:** `2c6158e` — «Бэкенд для 3 этапа. С готовыми 17 endpoints»
- **Удалено:** `SUMMARY.md` (не в индексе)

---
