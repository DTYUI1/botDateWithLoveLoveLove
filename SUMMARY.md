# ConnectMe Bot — Summary

## 📋 Статус
- **simple_bot.py** — работает ✅ (минимальный бот без backend)
- **main.py** — требует доработки (проблемы с подключением к backend через прокси)
- **Backend API** — работает ✅ (порт 8005)
- **Infrastructure** — работает ✅ (PostgreSQL, Redis, RabbitMQ, MinIO в Docker)

## 🔧 Что исправлено
1. **Токен бота** — обновлён на `YOUR_TELEGRAM_BOT_TOKEN_HERE` (@HUScorp_bot)
2. **ForeignKey** — добавлен в `backend/models/profile.py` (`user_id` → `users.id`)
3. **Прокси Telegram** — `AiohttpSession(proxy="http://127.0.0.1:7897")` работает
4. **Backend для localhost** — `trust_env=False` + очистка env переменных в `api_client.py`
5. **Логирование** — добавлено во все ключевые точки

## 🐛 Найденные проблемы
1. Кастомная `ProxyAiohttpSession` с httpx не работала для отправки сообщений
2. `httpx.AsyncClient` читает HTTP_PROXY даже с `trust_env=False` — решено через `os.environ.pop()`
3. `default=ParseMode.HTML` → `default=DefaultBotProperties(parse_mode=ParseMode.HTML)`

## 📁 Файлы
| Файл | Статус | Описание |
|------|--------|----------|
| `bot/simple_bot.py` | ✅ Работает | Минимальный бот, отвечает на /start |
| `bot/main.py` | ⚠️ Чинить | Полный бот с backend, middleware |
| `bot/test_bot.py` | ✅ Работал | Тестовый минимальный бот |
| `bot/api_client.py` | ✅ Исправлен | Клиент к backend с отключением прокси |
| `bot/handlers/start.py` | ✅ Логирование | Обработчик /start |
| `bot/middlewares/auth.py` | ✅ Логирование | Авторизация через backend |
| `backend/models/profile.py` | ✅ Исправлен | Добавлен ForeignKey |
| `backend/api/v1/auth.py` | ✅ Логирование | Endpoint авторизации |
| `backend/api/v1/profile.py` | ✅ Логирование | Endpoint профиля |

## 🚀 Запуск

### Simple бот (работает)
```bash
cd /home/artwox/orchestrAI/loveBot/projects/connectme
PYTHONPATH=. HTTP_PROXY="http://127.0.0.1:7897" HTTPS_PROXY="http://127.0.0.1:7897" \
  .venv/bin/python bot/simple_bot.py
```

### Infrastructure (Docker)
```bash
cd /home/artwox/orchestrAI/loveBot/projects/connectme
docker compose -f docker-compose.infra.yml up -d
```

### Backend
```bash
cd /home/artwox/orchestrAI/loveBot/projects/connectme/backend
DATABASE_URL="postgresql+asyncpg://connectme_user:connectme_secure_pass@127.0.0.1:5432/connectme_db" \
  ../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8005
```

## 🔑 Ключевые параметры
- **VPN прокси:** `http://127.0.0.1:7897` (Koala Clash)
- **Bot токен:** `YOUR_TELEGRAM_BOT_TOKEN_HERE`
- **Bot username:** `@HUScorp_bot`
- **Backend:** `http://localhost:8005`
