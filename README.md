# ConnectMe

[![CI configured](https://img.shields.io/badge/CI-GitHub%20Actions-blue)](.github/workflows/ci.yml)

**Страшно подойти первым? Не знаешь, что написать, чтобы не быть банальным?**


## 🚀 Быстрый старт

### Предварительные требования

- Docker >= 24.0
- Docker Compose >= 2.20
- Python 3.11+

### Установка

1. Скопируйте переменные окружения:
```bash
cp .env.example .env
```

2. Отредактируйте `.env` и заполните **все REQUIRED-переменные** (см. ниже).

3. Запустите сервисы:
```bash
docker compose up -d
```

4. Проверьте статус:
```bash
docker compose ps
```

### 🔐 Переменные окружения и секреты

Все секреты живут в `.env` (в git **не коммитим**) и валидируются прямо в
`docker-compose*.yml` через `${VAR:?...}` — запуск без `.env` или с пустым
секретом падает с понятным сообщением (`error while interpolating ...
POSTGRES_PASSWORD не задан в .env`).

Обязательные переменные (см. шаблон в `.env.example`):

| Переменная | Где используется | Комментарий |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | bot, match_consumer | Токен от @BotFather |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | backend, db, celery | Не используйте дефолтные значения |
| `RABBITMQ_USER` / `RABBITMQ_PASSWORD` | backend, bot, consumers, rabbitmq | Не использовать `guest/guest` |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | backend, minio | Задать локальные значения, не использовать публичные dev-default credentials |
| `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` | grafana (prod overlay) | Только для prod-сборки |

Генерация надёжного пароля:

```bash
openssl rand -base64 32
```

CI проверяет отсутствие секретов в репозитории через
[`gitleaks-action`](https://github.com/gitleaks/gitleaks-action) — см.
`.github/workflows/ci.yml`. Любой случайно закоммиченный секрет валит сборку.

## 📁 Структура проекта

```
connectme/
├── bot/                    # Telegram Bot (aiogram 3.x)
├── backend/                # Backend API (FastAPI)
├── monitoring/             # Prometheus + Grafana конфигурация
├── docs/                   # Документация
├── docker-compose.yml      # Docker Compose
├── .env.example            # Пример переменных окружения
└── README.md               # Этот файл
```

## 🏗️ Архитектура

См. [stage1_report.md](stage1_report.md) для полной документации.

### Основные сервисы:
- **Telegram Bot** — интерфейс пользователя
- **Backend API** — бизнес-логика (FastAPI)
- **PostgreSQL** — хранение данных
- **Redis** — кэширование анкет
- **RabbitMQ** — очереди событий
- **Celery Worker** — фоновые задачи
- **Minio** — хранение фотографий

## 🔧 Команды бота

| Команда | Описание |
|---------|----------|
| /start | Начать работу с ботом |
| /profile | Создать/редактировать анкету |
| /search | Поиск анкет |
| /matches | Список мэтчей |
| /settings | Настройки |

## 📊 Мониторинг

- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000 (admin/admin)

## 📝 Документация

- [Отчёт по Этапу 1](stage1_report.md)
- [Схема базы данных](database_schema.md)
- [DBML для dbdiagram.io](dbdiagram.dbml)

## 🧪 Тестирование

Подробности — в [`tests/README.md`](tests/README.md).

```bash
# Unit-тесты (моки, без сервисов)
.venv/bin/python -m pytest tests/ -v

# Полный прогон (unit + infra) — infra тесты пропускаются без сервисов
bash scripts/run-tests.sh
```

### Нагрузочное тестирование (Locust)

Полная инструкция — [`tests/load/README.md`](tests/load/README.md), отчёт —
[`docs/stages/stage4_loadtest.md`](docs/stages/stage4_loadtest.md).

```bash
pip install locust httpx
bash tests/load/seed.sh 100
mkdir -p tests/load/results
locust -f tests/load/locustfile.py --host http://localhost:8005 \
       --users 50 --spawn-rate 10 --run-time 60s --headless \
       --csv tests/load/results/run --csv-full-history

# Endpoint-focused проверка 50+ RPS на /matching/next
bash tests/load/seed.sh 800 120
LOCUST_PRESEEDED_REQUESTERS=120 LOCUST_RPS_PER_USER=2.05 \
       LOCUST_ENDPOINT=next locust -f tests/load/locustfile_endpoint.py \
       --host http://localhost:8005 --users 25 --spawn-rate 50 \
       --run-time 60s --headless \
       --csv tests/load/results/endpoint_next --csv-full-history
```

## 🚢 Production deploy

Production-конфигурация подключает RabbitMQ, MinIO, Celery worker/beat, nginx,
Prometheus и Grafana поверх базового стека.

```bash
cp .env.example .env        # заполнить секреты
bash scripts/deploy.sh      # build + up + health-check
```

Доступные интерфейсы:

| Сервис     | URL                              |
|------------|----------------------------------|
| API        | `http://<host>/api/v1/health`    |
| Grafana    | `http://<host>:3000`             |
| Prometheus | `http://<host>:9090`             |
| RabbitMQ   | `http://<host>:15672`            |
| MinIO      | `http://<host>:9001`             |

Бэкап БД (cron на хосте): `bash scripts/backup-db.sh` — дамп в `./backups/` с
ротацией (хранятся 14 последних).

## 📝 Лицензия

MIT License

---

*Создано с помощью автономной системы loveBot.*
