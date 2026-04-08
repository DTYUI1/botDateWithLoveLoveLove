# ConnectMe — Структура проекта

> **Дата актуализации:** 8 апреля 2026 г.
> **Версия:** 1.0.0
> **Тип:** Dating-бот в Telegram с микросервисной архитектурой

---

## 📋 Оглавление

1. [Общее описание](#общее-описание)
2. [Корневая структура](#корневая-структура)
3. [Backend (FastAPI)](#backend-fastapi)
4. [Bot (aiogram 3.x)](#bot-aiogram-3x)
5. [Инфраструктура](#инфраструктура)
6. [Документация](#документация)
7. [Скрипты и конфигурация](#скрипты-и-конфигурация)
8. [Технологический стек](#технологический-стек)
9. [Архитектурные решения](#архитектурные-решения)
10. [Текущий статус](#текущий-статус)

---

## Общее описание

**ConnectMe** — это умный dating-бот для Telegram, который помогает пользователям 18-35 лет находить серьёзные отношения. Бот не только подбирает пары по интересам и рейтингу, но и предоставляет удобный интерфейс для общения.

### Ключевые возможности
- Регистрация и создание детальных анкет
- Поиск и свайп анкет (лайк/пропуск)
- Система мэтчей при взаимных лайках
- Чат с мэтчами
- Многоуровневая система рейтингов
- Идеи для свиданий
- Кэширование анкет в Redis (10 анкет на сессию)

---

## Корневая структура

```
connectme/
├── .env.example              # Шаблон переменных окружения
├── .gitignore                # Исключения для Git
├── architecture.json         # Полная архитектурная спецификация
├── database_schema.json      # Схема базы данных (PostgreSQL)
├── dbdiagram.dbml            # DBML для визуализации схемы (dbdiagram.io)
├── docker-compose.yml        # Полный Docker Compose (все сервисы)
├── docker-compose.infra.yml  # Только инфраструктура (DB, Redis, RabbitMQ, MinIO)
├── prd.json                  # Product Requirements Document
├── README.md                 # Краткое руководство
├── SUMMARY.md                # Сводка по текущему статусу разработки
├── start-all.sh              # Скрипт локального запуска (backend + bot)
├── tracking_table.md         # Трекинг задач
│
├── backend/                  # Backend API (FastAPI)
├── bot/                      # Telegram Bot (aiogram 3.x)
├── docs/                     # Документация проекта
│   ├── info/                 # Справочная информация
│   ├── stages/               # Отчёты по этапам разработки
│   └── temp/                 # Временные файлы
└── logs/                     # Логи приложения (git-ignored)
```

---

## Backend (FastAPI)

**Путь:** `backend/`
**Технологии:** FastAPI, SQLAlchemy, asyncpg, Pydantic v2
**Порт:** 8005 (локально) / 8000 (в Docker)

### Структура

```
backend/
├── __init__.py
├── main.py                   # Точка входа: FastAPI приложение, lifespan, роутеры
├── Dockerfile                # Образ для Docker
├── requirements.txt          # Зависимости Python
│
├── api/                      # API роутеры
│   ├── __init__.py
│   └── v1/                   # Версия API v1
│       ├── auth.py           # Аутентификация через Telegram ID
│       ├── profile.py        # CRUD профилей
│       ├── matching.py       # Свайпы, подбор анкет
│       └── health.py         # Health check endpoint
│
├── core/                     # Базовая конфигурация
│   ├── __init__.py
│   ├── config.py             # Настройки приложения (env variables)
│   └── database.py           # Инициализация БД, session pool
│
├── models/                   # SQLAlchemy модели
│   ├── __init__.py
│   ├── user.py               # Пользователи (users)
│   ├── profile.py            # Профили (profiles)
│   ├── photo.py              # Фотографии (photos)
│   ├── swipe.py              # Свайпы (swipes)
│   ├── match.py              # Мэтчи (matches)
│   ├── message.py            # Сообщения (messages)
│   └── rating.py             # Рейтинги (ratings_*)
│
├── schemas/                  # Pydantic схемы валидации
│   └── ...
│
└── services/                 # Бизнес-логика
    ├── __init__.py
    └── profile_service.py    # Сервис профилей
```

### Основные эндпоинты API

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/v1/auth/telegram` | Аутентификация по Telegram ID |
| GET | `/api/v1/profile` | Получение своего профиля |
| POST | `/api/v1/profile` | Создание профиля |
| PUT | `/api/v1/profile` | Обновление профиля |
| POST | `/api/v1/profile/photo` | Загрузка фотографии |
| GET | `/api/v1/matching/next` | Следующая анкета (из кэша Redis) |
| POST | `/api/v1/matching/swipe` | Лайк/пропуск анкеты |
| GET | `/api/v1/matches` | Список мэтчей |
| GET | `/api/v1/messages/{match_id}` | История сообщений |
| POST | `/api/v1/messages/{match_id}` | Отправка сообщения |
| GET | `/api/v1/rating/my` | Мой рейтинг |
| GET | `/api/v1/health` | Health check |

---

## Bot (aiogram 3.x)

**Путь:** `bot/`
**Технологии:** aiogram 3.x, aiohttp, httpx
**Прокси:** Требуется для доступа к Telegram API (`http://127.0.0.1:7897`)

### Структура

```
bot/
├── __init__.py
├── main.py                   # Точка входа: Bot, Dispatcher, polling
├── simple_bot.py             # Минимальный рабочий бот (для тестов)
├── test_bot.py               # Тестовый бот
├── api_client.py             # HTTP-клиент для Backend API
├── config.py                 # Настройки бота (env variables)
├── states.py                 # FSM состояния для диалогов
├── Dockerfile                # Образ для Docker
├── requirements.txt          # Зависимости Python
│
├── handlers/                 # Обработчики команд
│   ├── __init__.py
│   ├── start.py              # /start — регистрация
│   ├── profile.py            # /profile — создание/редактирование анкеты
│   ├── search.py             # /search — поиск анкет
│   └── matches.py            # /matches — список мэтчей
│
├── middlewares/              # Middleware
│   ├── __init__.py
│   └── auth.py               # Авторизация через backend
│
├── keyboards/                # Inline-клавиатуры
│   ├── __init__.py
│   └── inline.py             # Кнопки: ❤️ Лайк, ❌ Пропустить, и т.д.
│
└── logs/                     # Логи бота
```

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начать работу с ботом, регистрация |
| `/profile` | Просмотр и редактирование своего профиля |
| `/search` | Начать поиск анкет для лайков |
| `/matches` | Просмотр списка мэтчей |
| `/settings` | Настройки предпочтений и уведомлений |

---

## Инфраструктура

### Docker Compose сервисы

#### 1. PostgreSQL (`db`)
- **Образ:** `postgres:15-alpine`
- **Порт:** 5432
- **Назначение:** Основное хранилище данных
- **Таблицы:** users, profiles, preferences, photos, swipes, matches, messages, ratings_*, reports, blocks, referrals, sessions, daily_limits, date_ideas, ai_prompts, analytics_events
- **Расширения:** PostGIS, JSONB

#### 2. Redis (`redis`)
- **Образ:** `redis:7-alpine`
- **Порт:** 6379
- **Назначение:** 
  - Кэширование анкет (`ranked_profiles:{user_id}:{session_id}`)
  - Брокер Celery
  - Rate limiting
- **TTL:** 3600 секунд

#### 3. RabbitMQ (`rabbitmq`)
- **Образ:** `rabbitmq:3-management-alpine`
- **Порты:** 5672 (AMQP), 15672 (Management UI)
- **Назначение:** Асинхронная обработка событий
- **Exchange-и:** swipe_events, match_events, rating_updates, chat_messages

#### 4. MinIO (`minio`)
- **Образ:** `minio/minio:latest`
- **Порты:** 9000 (API), 9001 (Console)
- **Назначение:** S3-совместимое хранилище фотографий
- **Бакет:** `profile-photos` (private)

#### 5. Backend API (`backend`)
- **Фреймворк:** FastAPI + Uvicorn
- **Порт:** 8005 (маппинг на 8000 в контейнере)
- **Зависимости:** PostgreSQL, Redis
- **Health check:** `/api/v1/health`

#### 6. Telegram Bot (`bot`)
- **Фреймворк:** aiogram 3.x
- **Зависимости:** Backend API
- **Особенность:** Требует прокси для доступа к Telegram API

---

## Документация

### `docs/info/` — Справочная информация
| Файл | Описание |
|------|----------|
| `architecture.md` | Архитектура системы |
| `database_schema.md` | Схема базы данных |
| `services.md` | Описание сервисов |
| `dbreview.md` | Обзор базы данных |
| `DB.png` | Визуальная схема БД |

### `docs/stages/` — Отчёты по этапам
| Файл | Описание |
|------|----------|
| `stage1_report.md` | Отчёт по Этапу 1 (планирование) |
| `stage2_report.md` | Отчёт по Этапу 2 (разработка) |

### `docs/temp/` — Временные файлы
Пустая директория для временных артефактов.

### Корневые JSON-документы
| Файл | Описание |
|------|----------|
| `architecture.json` | Полная архитектурная спецификация (сервисы, диаграммы, API, data flow, метрики) |
| `database_schema.json` | Детальная схема БД (таблицы, колонки, индексы, FK, enum-ы) |
| `prd.json` | Product Requirements Document (требования, user stories, критерии успеха) |

---

## Скрипты и конфигурация

### `.env.example`
Шаблон переменных окружения:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
POSTGRES_USER=connectme_user
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=connectme_db
REDIS_URL=redis://redis:6379/0
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=connectme-photos
OPENROUTER_API_KEY=your_openrouter_api_key_here
LOG_LEVEL=INFO
DEBUG=false
```

### `docker-compose.yml`
Полный стек: bot + backend + PostgreSQL + Redis

### `docker-compose.infra.yml`
Только инфраструктура: PostgreSQL + Redis + RabbitMQ + MinIO

### `start-all.sh`
Скрипт для локального запуска backend и bot с прокси:
- Запускает backend на порту 8005
- Запускает bot
- Устанавливает прокси `http://127.0.0.1:7897` (Koala Clash)
- Использует локальную БД, Redis, RabbitMQ

---

## Технологический стек

### Backend
- **FastAPI** — асинхронный веб-фреймворк
- **SQLAlchemy 2.x** — ORM
- **asyncpg** — асинхронный драйвер PostgreSQL
- **Pydantic v2** — валидация данных
- **Uvicorn** — ASGI сервер
- **Loguru** — логирование

### Bot
- **aiogram 3.x** — асинхронный фреймворк для Telegram Bot API
- **aiohttp** — HTTP-клиент с поддержкой прокси
- **httpx** — HTTP-клиент для Backend API
- **Loguru** — логирование

### Инфраструктура
- **PostgreSQL 15+** — реляционная БД с PostGIS и JSONB
- **Redis 7+** — кэш, брокер Celery, rate limiting
- **RabbitMQ 3.12+** — очередь сообщений
- **MinIO** — S3-совместимое хранилище
- **Docker & Docker Compose** — контейнеризация

### Планируемые (не реализованы)
- **Celery 5.x** — фоновые задачи (пересчёт рейтингов, очистка сессий)
- **Prometheus + Grafana** — мониторинг и визуализация метрик

---

## Архитектурные решения

### Микросервисная архитектура

```
┌─────────────┐
│   Telegram   │
│   Client     │
└──────┬──────┘
       │ commands, messages
       ▼
┌─────────────────────────┐
│  Telegram Bot Service   │  ← aiogram 3.x
│  (commands, keyboards)  │
└──────┬──────────────────┘
       │ REST API
       ▼
┌─────────────────────────┐
│    API Gateway          │  ← FastAPI
│  (auth, routing)        │
└──────┬──────────────────┘
       │
       ├──────────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Profile  │  │ Matching │  │  Chat    │  │  Media   │
│ Service  │  │ Service  │  │ Service  │  │ Service  │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │              │              │              │
     ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────┐
│                  PostgreSQL                         │
└─────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐
│    Redis     │         │   RabbitMQ   │
│ (cache 10)   │         │  (events)    │
└──────────────┘         └──────┬───────┘
                                │
                                ▼
                         ┌──────────────┐
                         │    Celery    │
                         │  (tasks)     │
                         └──────────────┘
```

### Система рейтингов

Многоуровневая система ранжирования пользователей:

1. **Первичный рейтинг** (on_profile_update)
   - Полнота анкеты (30%)
   - Качество фото (30%)
   - Соответствие предпочтениям (20%)
   - Верификация (20%)

2. **Поведенческий рейтинг** (daily via Celery)
   - Полученные лайки (25%)
   - Соотношение лайков/пропусков (25%)
   - Частота мэтчей (20%)
   - Инициирование диалогов (15%)
   - Паттерн активности (15%)

3. **Комбинированный рейтинг** (daily via Celery)
   - Формула: `combined = (primary * 0.4) + (behavioral * 0.4) + (referral_bonus * 0.2)`

### Кэширование анкет

- При начале сессии загружается 10 анкет в Redis
- Ключ: `ranked_profiles:{user_id}:{session_id}`
- TTL: 3600 секунд
- Обновление: при завершении сессии

### Data Flow примеры

1. **Регистрация:** Telegram → Bot → API Gateway → Profile Service → PostgreSQL → Rating Service
2. **Подбор анкет:** Telegram → Bot → API → Matching Service → Redis (cache) → PostgreSQL (miss) → Redis (cache 10) → Bot → Telegram
3. **Лайк:** Telegram → Bot → API → Matching Service → PostgreSQL (swipe) → RabbitMQ → Celery → Rating Service → PostgreSQL
4. **Мэтч:** Matching Service → PostgreSQL (mutual like) → RabbitMQ → Celery → Bot → Telegram (notify)

---

## Текущий статус

### ✅ Работает
- **Infrastructure:** PostgreSQL, Redis, RabbitMQ, MinIO (Docker Compose)
- **Backend API:** FastAPI приложение на порту 8005 (health check, auth, profile, matching роутеры)
- **Simple Bot:** Минимальный бот, отвечает на `/start`

### ⚠️ Требует доработки
- **Main Bot:** Полный бот с middleware и backend интеграцией (проблемы с подключением через прокси)
- **Celery Worker:** Фоновые задачи не реализованы
- **Chat Service:** WebSocket чат не реализован
- **Rating Service:** Автоматический пересчёт рейтингов не реализован
- **Media Service:** Загрузка фото через MinIO не реализована

### 📝 Запланировано
- Фаза 3: Система анкет и ранжирования (Redis кэширование, алгоритм подбора)
- Фаза 4: Дополнительные функции (Celery задачи, идеи для свиданий, тестирование, деплой)

### 🔑 Известные проблемы и решения
1. **Прокси для Telegram:** Используется `AiohttpSession(proxy="http://127.0.0.1:7897")`
2. **HTTP_PROXY для httpx:** `trust_env=False` + `os.environ.pop()` в `api_client.py`
3. **ForeignKey:** Добавлен в `backend/models/profile.py` (`user_id` → `users.id`)
4. **aiogram v3 синтаксис:** `default=DefaultBotProperties(parse_mode=ParseMode.HTML)`

---

## Быстрый старт

### 1. Инфраструктура
```bash
docker compose -f docker-compose.infra.yml up -d
```

### 2. Backend
```bash
cd backend
DATABASE_URL="postgresql+asyncpg://connectme_user:connectme_secure_pass@127.0.0.1:5432/connectme_db" \
REDIS_URL="redis://127.0.0.1:6379/0" \
RABBITMQ_URL="amqp://guest:guest@127.0.0.1:5672//" \
../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8005
```

### 3. Bot (с прокси)
```bash
PYTHONPATH=. HTTP_PROXY="http://127.0.0.1:7897" HTTPS_PROXY="http://127.0.0.1:7897" \
.venv/bin/python bot/simple_bot.py
```

### Или всё сразу
```bash
./start-all.sh
```

---
