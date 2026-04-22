# ConnectMe — Фактическая структура проекта

> Актуально на 22 апреля 2026
> Ветка: `stage1`
> Основано на реальном состоянии файлов и кода в репозитории, а не на плановых артефактах

## Назначение проекта

`ConnectMe` — Telegram dating-бот с отдельным ботом на `aiogram` и backend API на `FastAPI`.
Сейчас проект фактически устроен как связка:

1. Telegram Bot принимает команды и callback-и.
2. Bot ходит в backend по HTTP через `bot/api_client.py`.
3. Backend работает с PostgreSQL и опционально использует Redis.
4. RabbitMQ и MinIO подготовлены инфраструктурно, но интегрированы частично.

## Ключевые выводы по состоянию проекта

- Бот и backend уже связаны и покрывают основной сценарий: регистрация, анкета, поиск, свайпы, мэтчи, рейтинг, настройки, фото.
- Backend реализован как одно FastAPI-приложение, а не как набор отдельных микросервисов.
- Фото сейчас валидируются и записываются в БД, но фактическая загрузка/удаление в MinIO помечены как `TODO`.
- В `matching` есть заготовка под Redis-кэш сессий и fallback на прямой запрос к БД.
- В UI бота есть несколько кнопок без обработчиков: `settings`, `back_to_profile`, `open_chat`, `date_ideas`.
- В репозитории есть как минимум два набора тестов: `test/` и `tests/`.

## Корень проекта

```text
connectme/
├── .dockerignore
├── .env
├── .env.local
├── .gitignore
├── README.md
├── architecture.json
├── database_schema.json
├── dbdiagram.dbml
├── docker-compose.yml
├── docker-compose.infra.yml
├── prd.json
├── start-all.sh
├── tracking_table.md
├── bot_nohup.log
│
├── backend/                # FastAPI backend
├── bot/                    # Telegram bot на aiogram
├── docs/                   # Документация
├── infrastructure/         # Конфиги и утилиты инфраструктуры
├── logs/                   # Логи локального запуска
├── practice/               # Вспомогательная локальная директория
├── promts/                 # Промпты для разработчиков/ассистентов
├── scripts/                # Скрипты автоматизации
├── test/                   # Unit/infrastructure tests
└── tests/                  # API/integration tests
```

## Backend

Путь: `backend/`

Точка входа: `backend/main.py`

Назначение:
- поднимает FastAPI-приложение;
- инициализирует БД и Redis в `lifespan`;
- подключает 7 API-роутеров;
- пишет логи в `logs/backend_YYYY-MM-DD.log`.

### Структура backend

```text
backend/
├── .dockerignore
├── .env
├── Dockerfile
├── main.py
├── requirements.txt
├── backend.log
│
├── api/
│   └── v1/
│       ├── auth.py
│       ├── health.py
│       ├── matching.py
│       ├── photos.py
│       ├── profile.py
│       ├── rating.py
│       └── settings.py
│
├── core/
│   ├── config.py
│   ├── database.py
│   └── redis_client.py
│
├── models/
│   ├── user.py
│   ├── profile.py
│   ├── photo.py
│   ├── swipe.py
│   ├── match.py
│   ├── message.py
│   └── rating.py
│
├── schemas/
│   ├── user.py
│   ├── profile.py
│   ├── match.py
│   ├── rating.py
│   └── settings.py
│
└── services/
    ├── profile_service.py
    ├── matching_service.py
    ├── photo_service.py
    └── rating_service.py
```

### Реально подключённые backend-роуты

Под префиксом `/api/v1`:

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/auth/telegram` | Получить или создать пользователя по Telegram ID |
| `GET` | `/profile` | Получить профиль |
| `POST` | `/profile` | Создать профиль |
| `PUT` | `/profile` | Обновить профиль |
| `POST` | `/profile/photo` | Загрузить фото |
| `GET` | `/profile/photo` | Список фото профиля |
| `DELETE` | `/profile/photo/{photo_id}` | Удалить фото |
| `POST` | `/profile/photo/{photo_id}/set-primary` | Сделать фото основным |
| `GET` | `/matching/next` | Следующая анкета |
| `POST` | `/matching/swipe` | Свайп по анкете |
| `GET` | `/matching/matches` | Список мэтчей |
| `POST` | `/matching/session/refresh` | Обновить сессию поиска |
| `GET` | `/matching/session/status` | Статус кэш-сессии |
| `GET` | `/rating/my` | Текущий рейтинг |
| `GET` | `/settings` | Настройки поиска |
| `PUT` | `/settings` | Обновить настройки поиска |
| `GET` | `/health` | Health check |

Дополнительно:
- `GET /` возвращает информацию о сервисе и ссылку на `/docs`.

### Что делает каждый сервис

- `profile_service.py`
  Работает с пользователями и профилями, обновляет анкету, записывает свайпы, формирует мэтчи.
- `matching_service.py`
  Подбирает анкеты, учитывает уже свайпнутые профили, применяет фильтры и может кэшировать сессию в Redis.
- `photo_service.py`
  Валидирует фото, создаёт записи о фото, переключает primary и делает soft delete.
- `rating_service.py`
  Содержит три уровня расчёта рейтинга: `Primary`, `Behavioral`, `Combined`.

### Важные факты по backend

- Backend использует `FastAPI`, `SQLAlchemy`, `asyncpg`, `pydantic-settings`, `redis`.
- `docker-compose.yml` публикует backend наружу как `8005:8000`.
- `backend/core/config.py` умеет искать `.env` сначала рядом с `backend/`, потом в корне проекта.
- `health.py` реально проверяет API, Redis и БД.

### Частично реализовано

- В `backend/api/v1/photos.py` загрузка в MinIO и удаление из MinIO пока не выполнены.
- В `backend/api/v1/matching.py` публикация событий в RabbitMQ и обновление Redis-счётчиков свайпов оставлены как `TODO`.
- Модель `message.py` есть, но отдельного Messages API в backend нет.

## Telegram Bot

Путь: `bot/`

Точка входа: `bot/main.py`

Назначение:
- поднимает `Bot` и `Dispatcher`;
- регистрирует `AuthMiddleware`;
- подключает роутеры;
- общается с backend через `APIClient`.

### Структура bot

```text
bot/
├── Dockerfile
├── api_client.py
├── config.py
├── main.py
├── simple_bot.py
├── states.py
├── test_bot.py
├── requirements.txt
│
├── handlers/
│   ├── common.py
│   ├── matches.py
│   ├── photos.py
│   ├── profile.py
│   ├── rating.py
│   ├── search.py
│   ├── settings.py
│   └── start.py
│
├── keyboards/
│   └── inline.py
│
├── middlewares/
│   └── auth.py
│
└── logs/
```

### Что реально делает бот

- `middlewares/auth.py`
  На каждом обновлении вызывает backend-авторизацию `POST /api/v1/auth/telegram`.
- `handlers/start.py`
  Обрабатывает `/start`, проверяет наличие профиля и запускает создание анкеты через FSM.
- `handlers/profile.py`
  Ведёт сценарий создания профиля и редактирования полей анкеты.
- `handlers/photos.py`
  Загружает фото через Telegram, кладёт их во временный файл и отправляет в backend.
- `handlers/search.py`
  Запускает подбор анкет, хранит `session_id` в FSM, отправляет лайки/пропуски.
- `handlers/matches.py`
  Показывает список мэтчей.
- `handlers/rating.py`
  Показывает рейтинг и краткую интерпретацию tier.
- `handlers/settings.py`
  Отображает текущие настройки и позволяет менять возраст, дистанцию и `looking_for`.
- `handlers/common.py`
  Даёт команду `/cancel`.

### Команды бота

Публичные команды, выставляемые через `set_my_commands`:

- `/start`
- `/profile`
- `/search`
- `/matches`
- `/rating`
- `/settings`
- `/cancel`

Дополнительные текстовые команды, которые есть в обработчиках, но не добавляются в список команд Telegram:

- `/settings_age`
- `/settings_distance`
- `/settings_looking`

### FSM-состояния

В `bot/states.py` есть две группы состояний:

- `ProfileStates`
  Создание и редактирование анкеты, плюс ожидание фото.
- `SearchStates`
  Просмотр анкет и изменение параметров поиска.

### APIClient

`bot/api_client.py` покрывает backend-методы для:

- auth/user;
- profile create/get/update;
- matching next/swipe/matches/refresh;
- photos upload/get/delete/set-primary;
- rating;
- settings;
- health check.

Особенность:
- при создании `httpx.AsyncClient` временно очищаются proxy env vars, чтобы локальные запросы к backend не уходили через прокси.

### Текущее состояние бота

Работает:
- авторизация через middleware;
- создание и редактирование анкеты;
- просмотр профиля;
- загрузка и удаление фото через backend;
- поиск анкет и свайпы;
- просмотр мэтчей;
- просмотр рейтинга;
- изменение настроек поиска.

Не доведено до конца:
- кнопка `⚙️ Настройки` в `profile_menu_keyboard()` имеет `callback_data="settings"`, но обработчика для этого callback нет;
- кнопка `⬅️ Назад к профилю` есть в клавиатурах, но обработчика `back_to_profile` нет;
- кнопки `💬 Написать` (`open_chat`) и `🎁 Идеи для свиданий` (`date_ideas`) не обработаны;
- `confirm_keyboard()` определена, но callback-обработчиков `confirm_yes` и `confirm_no` в проекте нет.

## Инфраструктура

Путь: `infrastructure/`

```text
infrastructure/
├── README.md
├── STAGE3_SETUP.md
├── VERIFICATION_REPORT.md
├── minio/
│   ├── minio_client.py
│   └── setup.sh
├── postgres/
│   ├── init.sql
│   └── postgresql.conf
├── rabbitmq/
│   ├── definitions.json
│   ├── event_publisher.py
│   └── rabbitmq.conf
└── redis/
    ├── cache_patterns.py
    └── redis.conf
```

### Compose-конфигурации

- `docker-compose.infra.yml`
  Поднимает `PostgreSQL`, `Redis`, `RabbitMQ`, `MinIO`.
- `docker-compose.yml`
  Поднимает `bot`, `backend`, `db`, `redis`.

Замечание:
- в основном `docker-compose.yml` сервисы `RabbitMQ` и `MinIO` не стартуют, хотя backend держит конфиг под них.

### Что уже интегрировано с кодом

- PostgreSQL используется backend-ом.
- Redis используется для health check, рейтингового кэша и matching session cache.
- RabbitMQ пока подготовлен инфраструктурно, но из backend не вызывается.
- MinIO подготовлен инфраструктурно, но upload/delete в API фото пока заглушены.

## Документация

Путь: `docs/`

```text
docs/
├── info/
│   ├── DB.png
│   ├── architecture.md
│   ├── database_schema.md
│   ├── dbreview.md
│   └── services.md
├── stages/
│   ├── stage1_report.md
│   ├── stage2_report.md
│   └── stage3_report.md
└── temp/
    ├── BACKEND_STATUS.md
    ├── BOT_LAUNCH_GUIDE.md
    ├── PROBLEMS_AND_SOLUTIONS.md
    ├── SUMMARY_ALL_WORK.md
    ├── SUMMARY_PHASE1.md
    └── project_structure.md
```

## Тесты

В проекте два отдельных набора тестов.

### `test/`

Назначение:
- unit- и infrastructure-тесты.

Содержимое:

```text
test/
├── infrastructure/
│   └── test_health_check.py
├── rabbitmq/
│   └── test_rabbitmq_publisher.py
├── redis/
│   └── test_redis_cache.py
├── services/
│   └── test_rating_service.py
├── README.md
├── pytest.ini
└── requirements.txt
```

### `tests/`

Назначение:
- интеграционные и API-тесты.

Содержимое:

```text
tests/
├── conftest.py
├── pytest.ini
├── requirements.txt
├── test_api_endpoints.py
└── test_stage3_integration.py
```

Замечание:
- в обеих директориях есть `.pytest_cache`, но это служебные артефакты, не часть логической структуры проекта.

## Скрипты

Путь: `scripts/`

```text
scripts/
├── health-check.sh
├── run-tests.sh
└── setup-infra.sh
```

Назначение:
- `setup-infra.sh` поднимает и настраивает инфраструктуру;
- `health-check.sh` проверяет сервисы;
- `run-tests.sh` запускает тестовые сценарии.

Дополнительно:
- `start-all.sh` в корне запускает backend и bot локально.

## Промпты

Путь: `promts/`

```text
promts/
├── backend_developer.md
├── queue_cache_engineer.md
└── telegram_bot_developer.md
```

## Что в документе было обновлено

По сравнению с предыдущей версией документа были исправлены ключевые расхождения:

- убраны неподтверждённые утверждения вроде "всё работает", "17/17 endpoints → 200 OK", "ветка опережает origin на 2 коммита";
- отражены реальные директории `docs/temp/`, `practice/`, `logs/`, `bot/logs/`;
- уточнено, что в bot не 6, а 8 handler-модулей;
- уточнено, что backend содержит 7 router-модулей и 17 API-endpoint-ов под `/api/v1`, плюс корневой `/`;
- добавлены реальные незавершённые места в Telegram UI и интеграциях MinIO/RabbitMQ;
- удалены ссылки на несуществующие каталоги и неподтверждённые результаты тестов.
