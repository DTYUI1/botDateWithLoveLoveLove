# ConnectMe — Архитектура системы

## Общая схема архитектуры

```mermaid
flowchart TB
    subgraph Client["📱 Клиентский слой"]
        TG[Telegram Client]
    end

    subgraph Bot["🤖 Telegram Bot Service"]
        BotSvc[aiogram 3.x Bot]
    end

    subgraph API["🌐 API Gateway Layer"]
        APIGW[FastAPI API Gateway]
    end

    subgraph Services["🔧 Микросервисы"]
        ProfileSvc[Profile Service]
        MatchingSvc[Matching Service]
        ChatSvc[Chat Service]
        RatingSvc[Rating Service]
        MediaSvc[Media Service]
    end

    subgraph Queue["📨 Message Queue"]
        RabbitMQ[RabbitMQ]
        SwipeEx[swipe_events]
        MatchEx[match_events]
        RatingEx[rating_updates]
        ChatEx[chat_messages]
    end

    subgraph Tasks["⚙️ Task Queue"]
        Celery[Celery Worker]
        Redis[(Redis)]
    end

    subgraph Storage["💾 Хранилища данных"]
        PostgreSQL[(PostgreSQL)]
        Minio[(Minio S3)]
    end

    subgraph Monitoring["📊 Monitoring"]
        Prometheus[Prometheus]
        Grafana[Grafana]
    end

    %% Клиент -> Бот
    TG -->|commands, messages| BotSvc

    %% Бот -> API Gateway
    BotSvc -->|REST API| APIGW

    %% API Gateway -> Сервисы
    APIGW --> ProfileSvc
    APIGW --> MatchingSvc
    APIGW --> ChatSvc
    APIGW --> MediaSvc

    %% Сервисы -> БД
    ProfileSvc --> PostgreSQL
    MatchingSvc --> PostgreSQL
    ChatSvc --> PostgreSQL
    RatingSvc --> PostgreSQL
    MediaSvc --> PostgreSQL

    %% Сервисы -> Redis (кэш)
    MatchingSvc -.->|кэш 10 анкет| Redis

    %% Сервисы -> RabbitMQ
    MatchingSvc -->|публикация событий| RabbitMQ
    ChatSvc -->|публикация сообщений| RabbitMQ

    %% RabbitMQ -> Exchanges
    RabbitMQ --> SwipeEx
    RabbitMQ --> MatchEx
    RabbitMQ --> RatingEx
    RabbitMQ --> ChatEx

    %% RabbitMQ -> Celery
    SwipeEx --> Celery
    MatchEx --> Celery
    RatingEx --> Celery
    ChatEx --> Celery

    %% Celery -> Redis
    Celery -->|брокер/результаты| Redis

    %% Celery -> PostgreSQL
    Celery -->|запись рейтингов| PostgreSQL

    %% Media Service -> Minio
    MediaSvc -->|загрузка фото| Minio

    %% Monitoring
    ProfileSvc -.->|метрики| Prometheus
    MatchingSvc -.->|метрики| Prometheus
    ChatSvc -.->|метрики| Prometheus
    RabbitMQ -.->|метрики| Prometheus
    Redis -.->|метрики| Prometheus
    PostgreSQL -.->|метрики| Prometheus

    Prometheus --> Grafana
```

---

## Описание компонентов

### 1. Telegram Bot Service
- **Технология:** aiogram 3.x
- **Роль:** Единственный интерфейс для пользователей
- **Режим работы:** Long-polling или Webhook
- **Взаимодействие:** REST запросы к API Gateway

### 2. API Gateway (Backend API)
- **Технология:** FastAPI
- **Роль:** Единая точка входа, аутентификация, маршрутизация
- **Порт:** 8000
- **Взаимодействие:** Оркестрация запросов к микросервисам

### 3. Profile Service
- **Технология:** FastAPI + PostgreSQL
- **Роль:** CRUD профилей пользователей
- **Порт:** 8001
- **Данные:** users, profiles, photos

### 4. Matching Service
- **Технология:** FastAPI + Redis + PostgreSQL
- **Роль:** Подбор и ранжирование анкет, свайпы, мэтчи
- **Порт:** 8002
- **Кэширование:** 10 анкет на сессию в Redis
- **Данные:** swipes, matches

### 5. Chat Service
- **Технология:** FastAPI + WebSocket
- **Роль:** Обмен сообщениями между мэтчами
- **Порт:** 8003
- **Данные:** messages

### 6. Rating Service
- **Технология:** Celery 5.x + PostgreSQL
- **Роль:** Расчёт многоуровневых рейтингов (первичный, поведенческий, комбинированный)
- **Порт:** N/A (фоновые задачи)
- **Данные:** ratings_primary, ratings_behavioral, ratings_combined

### 7. Media Service
- **Технология:** FastAPI + Minio SDK
- **Роль:** Загрузка, валидация и хранение фотографий профилей
- **Порт:** 8004
- **Данные:** photos, bucket profile-photos

