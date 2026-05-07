
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

2. Отредактируйте `.env` и добавьте ваши ключи:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
POSTGRES_PASSWORD=your_secure_password
```

3. Запустите сервисы:
```bash
docker-compose up -d
```

4. Проверьте статус:
```bash
docker-compose ps
```

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
