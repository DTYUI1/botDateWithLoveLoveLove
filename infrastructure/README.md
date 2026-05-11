# Инфраструктура ConnectMe

Эта папка содержит всю конфигурацию инфраструктуры для проекта ConnectMe.

## Структура

```
infrastructure/
├── postgres/
│   ├── postgresql.conf       # Настройки PostgreSQL (память, WAL, логи)
│   ├── init.sql              # Инициализация схемы БД
│   └── migrations/           # Папка для SQL миграций
│
├── redis/
│   ├── redis.conf            # Настройки Redis (кэш, персистентность)
│   └── cache_patterns.py     # Python утилиты для кэширования
│
├── rabbitmq/
│   ├── rabbitmq.conf         # Настройки RabbitMQ
│   ├── definitions.json      # Exchanges, queues, bindings
│   └── event_publisher.py    # Python publisher событий
│
└── minio/
    ├── setup.sh              # Скрипт настройки bucket'ов
    └── minio_client.py       # Python клиент для MinIO
```

## Быстрый старт

### 1. Запуск инфраструктуры

```bash
# Из корня проекта
./scripts/setup-infra.sh
```

### 2. Проверка здоровья

```bash
./scripts/health-check.sh
```

### 3. Запуск тестов

```bash
./scripts/run-tests.sh
```

## Сервисы

### PostgreSQL

- **Версия:** 15 Alpine
- **Порт:** 5432
- **Конфиг:** `infrastructure/postgres/postgresql.conf`
- **Инициализация:** `infrastructure/postgres/init.sql`

**Оптимизации:**
- shared_buffers = 256MB
- effective_cache_size = 1GB
- SSD оптимизация (random_page_cost = 1.1)
- Логирование медленных запросов (>1s)

**Подключение:**
```
host: localhost
port: 5432
user: connectme_user
password: <POSTGRES_PASSWORD из локального .env>
database: connectme_db
```

### Redis

- **Версия:** 7 Alpine
- **Порт:** 6379
- **Конфиг:** `infrastructure/redis/redis.conf`
- **Память:** 512MB max

**Паттерны кэширования:**
- `ranked_profiles:{user_id}:{session_id}` — кэш анкет (List)
- `ratings:{type}` — рейтинги (Sorted Set)
- `swipes:daily:{user_id}:{date}` — счётчики свайпов (Hash)

**Подключение:**
```
host: localhost
port: 6379
url: redis://localhost:6379/0
```

### RabbitMQ

- **Версия:** 3.12 Management
- **Порты:** 5672 (AMQP), 15672 (Management UI)
- **Конфиг:** `infrastructure/rabbitmq/rabbitmq.conf`

**Exchanges:**
- `swipe_events` (topic) — события свайпов
- `match_events` (topic) — события мэтчей
- `rating_updates` (topic) — обновления рейтинга
- `chat_messages` (topic) — сообщения чата

**Queues:**
- `swipe_processing` — обработка свайпов
- `match_notifications` — уведомления о мэтчах
- `rating_calculation` — расчёт рейтингов
- `message_delivery` — доставка сообщений

**Подключение:**
```
host: localhost
port: 5672
user: guest
password: <RABBITMQ_PASSWORD из локального .env>
Management UI: http://localhost:15672
```

### MinIO

- **Версия:** Latest
- **Порты:** 9000 (API), 9001 (Console)
- **Bucket:** profile-photos

**Подключение:**
```
endpoint: localhost:9000
access_key: <MINIO_ACCESS_KEY из локального .env>
secret_key: <MINIO_SECRET_KEY из локального .env>
Console: http://localhost:9001
```

## Интеграция с Backend

### Redis клиент

```python
from backend.core.redis_client import RedisClient

# Использование
async with RedisClient() as client:
    session_cache = client.get_session_cache()
    await session_cache.cache_profiles(user_id, session_id, profiles)
```

### Rating Service

```python
from backend.services.rating_service import RatingService
from backend.core.redis_client import RedisClient

async with RedisClient() as redis_client:
    rating_cache = redis_client.get_rating_cache()
    service = RatingService(db_session, rating_cache)
    
    # Рассчитать все рейтинги
    result = await service.calculate_all_ratings(profile)
```

### Matching Service

```python
from backend.services.matching_service import MatchingService
from backend.core.redis_client import RedisClient

async with RedisClient() as redis_client:
    session_cache = redis_client.get_session_cache()
    service = MatchingService(db_session, session_cache)
    
    # Начать сессию подбора
    result = await service.start_matching_session(telegram_id)
```

### Event Publisher

```python
from infrastructure.rabbitmq.event_publisher import EventPublisher

async with EventPublisher(rabbitmq_url) as publisher:
    await publisher.publish_swipe_event(
        from_user_id=100,
        to_user_id=200,
        action="like"
    )
```

### MinIO Client

```python
import os

from infrastructure.minio.minio_client import MinIOClient

client = MinIOClient(
    endpoint="localhost:9000",
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    bucket_name="profile-photos"
)

# Загрузить фото
url = await client.upload_photo(file, "user_123/photo_1.jpg")

# Получить временный URL
presigned_url = await client.get_presigned_url("user_123/photo_1.jpg")
```

## Скрипты

### setup-infra.sh

Полная установка инфраструктуры:
- Проверка Docker
- Создание .env
- Запуск сервисов
- Проверка здоровья
- Настройка MinIO

### health-check.sh

Проверка здоровья всех сервисов:
- Статус контейнеров
- PostgreSQL (подключение, таблицы)
- Redis (memory, keys)
- RabbitMQ (queues)
- MinIO (buckets)

### run-tests.sh

Запуск тестов:
- Установка зависимостей
- Запуск pytest
- Отчёт о результатах

## Переменные окружения

Все переменные в `.env`:

```bash
# PostgreSQL
POSTGRES_USER=connectme_user
POSTGRES_PASSWORD=REQUIRED_POSTGRES_PASSWORD
POSTGRES_DB=connectme_db

# Redis
REDIS_URL=redis://localhost:6379/0

# RabbitMQ
RABBITMQ_USER=REQUIRED_RABBITMQ_USER
RABBITMQ_PASSWORD=REQUIRED_RABBITMQ_PASSWORD

# MinIO
MINIO_ACCESS_KEY=REQUIRED_MINIO_ACCESS_KEY
MINIO_SECRET_KEY=REQUIRED_MINIO_SECRET_KEY
```

## Тесты

Все тесты в папке `test/`:

```bash
# Запустить все тесты
cd test && pytest -v

# Только тесты рейтинга (не требуют Docker)
pytest services/test_rating_service.py -v

# Только тесты Redis (требует Redis)
pytest redis/test_redis_cache.py -v

# Только тесты RabbitMQ (требует RabbitMQ)
pytest rabbitmq/test_rabbitmq_publisher.py -v
```

**Результат:** ✅ 24/24 теста прошли успешно

## Для нейросети-разработчика

Когда вы начнёте разработку Этапа 3, вот что уже готово:

### ✅ Готово

1. **PostgreSQL** — схема БД с таблицами рейтингов
2. **Redis** — паттерны кэширования (10 анкет на сессию)
3. **RabbitMQ** — очереди для событий
4. **MinIO** — S3 хранилище для фото
5. **RatingService** — 3 уровня алгоритмов
6. **MatchingService** — подбор анкет с рейтингом
7. **Тесты** — 24 теста для алгоритмов

### 🚀 Следующие шаги

1. Запустить инфраструкру: `./scripts/setup-infra.sh`
2. Проверить здоровье: `./scripts/health-check.sh`
3. Изучить тесты: `cd test && pytest services/test_rating_service.py -v`
4. Начать разработку задач из `tracking_table.md` (Этап 3)

## Troubleshooting

### Сервис не запускается

```bash
# Проверить логи
docker logs connectme-postgres
docker logs connectme-redis
docker logs connectme-rabbitmq
docker logs connectme-minio
```

### PostgreSQL не подключается

```bash
# Проверить что init.sql выполнился
docker exec connectme-postgres psql -U connectme_user -d connectme_db -c "\dt"
```

### Redis не сохраняет данные

```bash
# Проверить redis.conf
docker exec connectme-redis cat /usr/local/etc/redis/redis.conf
```

### RabbitMQ очереди не созданы

```bash
# Проверить definitions.json
docker exec connectme-rabbitmq cat /etc/rabbitmq/definitions.json
```
