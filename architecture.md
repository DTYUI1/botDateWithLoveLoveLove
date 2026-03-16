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
        IcebreakerSvc[Icebreaker Service]
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
    APIGW --> IcebreakerSvc
    APIGW --> MediaSvc

    %% Сервисы -> БД
    ProfileSvc --> PostgreSQL
    MatchingSvc --> PostgreSQL
    ChatSvc --> PostgreSQL
    IcebreakerSvc --> PostgreSQL
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
    IcebreakerSvc -.->|метрики| Prometheus
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

### 6. Icebreaker Service
- **Технология:** FastAPI + PostgreSQL
- **Роль:** Генерация вопросов для начала разговора
- **Порт:** 8004
- **Данные:** icebreaker_questions, icebreaker_usage

### 7. Rating Service
- **Технология:** Celery + PostgreSQL
- **Роль:** Расчёт многоуровневых рейтингов
- **Порт:** N/A (worker)
- **Данные:** ratings

### 8. Media Service
- **Технология:** FastAPI + Minio
- **Роль:** Загрузка и хранение фотографий
- **Порт:** 8005
- **Хранилище:** Minio S3

### 9. PostgreSQL
- **Роль:** Основное хранилище данных
- **Порт:** 5432
- **Расширения:** PostGIS для гео-запросов

### 10. Redis
- **Роль:** Кэш сессий, брокер Celery
- **Порт:** 6379
- **TTL кэша:** 3600 секунд

### 11. RabbitMQ
- **Роль:** Асинхронная обработка событий
- **Порт:** 5672 (AMQP), 15672 (Management)
- **Exchanges:** swipe_events, match_events, rating_updates, chat_messages

### 12. Celery Worker
- **Роль:** Фоновые задачи (пересчёт рейтингов, аналитика)
- **Расписание:** daily, hourly задачи

### 13. Minio
- **Роль:** S3-совместимое хранилище
- **Порт:** 9000 (API), 9001 (Console)
- **Buckets:** profile-photos (private), icebreaker-media (public)

---

## Потоки данных между сервисами

### Поток 1: Регистрация пользователя
```
Telegram → Bot Service → API Gateway → Profile Service → PostgreSQL
                                    ↓
                              Rating Service → PostgreSQL (создание рейтинга)
```

### Поток 2: Загрузка фотографии
```
Telegram → Bot Service → API Gateway → Media Service → Minio
                                    ↓
                              Profile Service → PostgreSQL (метаданные)
                                    ↓
                              Rating Service → PostgreSQL (обновление photo_score)
```

### Поток 3: Подбор анкет (с кэшированием)
```
Telegram → Bot Service → API Gateway → Matching Service → Redis (проверка кэша)
                                                      ↓ (cache miss)
                                              PostgreSQL (запрос анкет)
                                                      ↓
                                              Redis (запись 10 анкет)
                                                      ↓
                                              Bot Service → Telegram (показ анкеты)
```

### Поток 4: Лайк анкеты
```
Telegram → Bot Service → API Gateway → Matching Service → PostgreSQL (запись swipe)
                                                      ↓
                                              RabbitMQ (swipe_events)
                                                      ↓
                                              Celery Worker → Rating Service
                                                      ↓
                                              PostgreSQL (обновление рейтинга)
```

### Поток 5: Создание мэтча
```
Matching Service → PostgreSQL (проверка взаимного лайка)
              ↓ (match found)
        PostgreSQL (создание match)
              ↓
        RabbitMQ (match_events)
              ↓
        Celery Worker → Chat Service (создание чата)
              ↓
        Bot Service → Telegram (уведомление обоих пользователей)
```

### Поток 6: Отправка сообщения
```
Telegram → Bot Service → API Gateway → Chat Service → PostgreSQL (сохранение)
                                                    ↓
                                            RabbitMQ (chat_messages)
                                                    ↓
                                            Bot Service → Telegram (доставка получателю)
```

### Поток 7: Ледокол (icebreaker вопрос)
```
Telegram → Bot Service → API Gateway → Icebreaker Service → PostgreSQL (выбор вопроса)
                                                          ↓
                                                  PostgreSQL (запись usage统计)
                                                          ↓
                                                  Chat Service → PostgreSQL (сообщение)
                                                          ↓
                                                  Bot Service → Telegram (отправка)
```

### Поток 8: Ежедневный пересчёт рейтингов
```
Celery Beat → Celery Worker → PostgreSQL (чтение свайпов, мэтчей)
                          ↓
                    Rating Service (расчёт behavioral_score)
                          ↓
                    PostgreSQL (обновление combined_score)
```

---

## Схема взаимодействия для функции «Ледокол»

```mermaid
sequenceDiagram
    participant U as Пользователь
    participant B as Bot Service
    participant G as API Gateway
    participant I as Icebreaker Service
    participant C as Chat Service
    participant DB as PostgreSQL
    participant R as Recipient

    U->>B: /icebreaker или кнопка 🧊 Ледокол
    B->>G: POST /api/v1/icebreaker/get_question<br/>{match_id, user_id}
    G->>I: Запрос вопроса
    I->>DB: SELECT вопрос WHERE<br/>category IN (interests)<br/>ORDER BY success_rate DESC<br/>LIMIT 1
    DB-->>I: Вопрос + метаданные
    I->>DB: INSERT icebreaker_usage<br/>(question_id, sender_id,<br/>recipient_id, match_id)
    DB-->>I: OK
    I-->>G: {question_text, category,<br/>difficulty, question_id}
    G-->>B: Вопрос для отправки
    B->>C: POST /api/v1/messages/send<br/>{match_id, content, type: icebreaker}
    C->>DB: INSERT message<br/>(match_id, sender_id,<br/>content, message_type)
    DB-->>C: OK
    C-->>B: Message created
    B->>U: 🧊 Вопрос отправлен!<br/>"{{question_text}}"
    B->>R: 💬 Новое сообщение от матча!<br/>"{{question_text}}"
    
    Note over I,R: Вопрос помечается как<br/>message_type = 'icebreaker'<br/>для аналитики
```

### Детали функции «Ледокол»

**Шаг 1: Инициация**
- Пользователь нажимает кнопку «🧊 Ледокол» в чате с мэтчем
- Или вводит команду `/icebreaker`

**Шаг 2: Подбор вопроса**
- Icebreaker Service получает контекст:
  - `match_id` — идентификатор мэтча
  - `user_id` — отправитель
  - `recipient_id` — получатель
  - Интересы обоих пользователей (из Profile Service)
- Алгоритм выбора:
  1. Фильтрация по категориям, соответствующим интересам
  2. Приоритет вопросам с высоким `success_rate`
  3. Исключение недавно использованных вопросов
  4. Учёт уровня сложности (`light` для новых мэтчей)

**Шаг 3: Отправка**
- Вопрос отправляется как сообщение от имени пользователя
- Тип сообщения: `message_type = 'icebreaker'`
- Запись в `icebreaker_usage` для отслеживания эффективности

**Шаг 4: Аналитика**
- Если получатель ответил → `was_responded = true`
- Success rate вопроса обновляется периодически через Celery

**Категории вопросов:**
- `general` — общие вопросы о жизни
- `hobbies` — увлечения и интересы
- `travel` — путешествия
- `food` — еда и рестораны
- `entertainment` — фильмы, музыка, книги
- `deep` — глубокие философские вопросы

**Уровни сложности:**
- `light` — лёгкие, непринуждённые вопросы
- `medium` — требуют размышления
- `deep` — личные, глубокие темы

---

## Масштабирование

### Горизонтальное масштабирование
- **Bot Service:** Несколько инстансов через webhook
- **API Gateway:** Load balancer (nginx/HAProxy)
- **Микросервисы:** Kubernetes pods с auto-scaling
- **Celery:** Несколько worker процессов

### Вертикальное масштабирование
- **PostgreSQL:** Репликация (master-slave)
- **Redis:** Cluster mode
- **RabbitMQ:** Federation plugin

### Кэширование
- **Redis:** 10 анкет на сессию
- **TTL:** 3600 секунд
- **Ключ:** `ranked_profiles:{user_id}:{session_id}`
- **Стратегия:** Refresh на последней анкете

---

## Безопасность

- **Аутентификация:** По Telegram ID (верификация через Bot API)
- **Авторизация:** Проверка владения ресурсом (profile_id, match_id)
- **Rate Limiting:** Redis-based (ограничение действий в минуту)
- **Валидация:** Pydantic схемы на всех входах
- **Шифрование:** HTTPS для всех внешних соединений
- **Хранение фото:** Private bucket с presigned URLs
