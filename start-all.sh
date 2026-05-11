#!/bin/bash
# Запуск ConnectMe бота и backend (локальный dev)
set -e

cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"
RUN_DIR="$PROJECT_ROOT/.run"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$RUN_DIR" "$LOG_DIR"

if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    . "$PROJECT_ROOT/.env"
    set +a
fi

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${RABBITMQ_USER:?RABBITMQ_USER is required}"
: "${RABBITMQ_PASSWORD:?RABBITMQ_PASSWORD is required}"

export PYTHONPATH=.
export HTTP_PROXY="http://127.0.0.1:7897"
export HTTPS_PROXY="http://127.0.0.1:7897"
export ALL_PROXY="http://127.0.0.1:7897"
export http_proxy="$HTTP_PROXY"
export https_proxy="$HTTPS_PROXY"
export all_proxy="$ALL_PROXY"

# Останавливаем предыдущие запуски, если есть
if [ -x "$PROJECT_ROOT/stop-all.sh" ]; then
    "$PROJECT_ROOT/stop-all.sh" --quiet || true
fi

# === Backend ===
cd "$PROJECT_ROOT/backend"
# httpx/asyncpg/redis для backend ходят на localhost — прокси выключаем для backend-процесса
DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}" \
REDIS_URL="redis://127.0.0.1:6379/0" \
RABBITMQ_URL="amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@127.0.0.1:5672//" \
HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" http_proxy="" https_proxy="" all_proxy="" \
nohup ../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8005 \
    > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$RUN_DIR/backend.pid"
echo "[start] Backend PID: $BACKEND_PID  (лог: $LOG_DIR/backend.log)"

# Ждём, пока backend поднимется
cd "$PROJECT_ROOT"
echo -n "[start] Жду backend на :8005"
for i in {1..30}; do
    if curl -s -f http://127.0.0.1:8005/api/v1/health > /dev/null 2>&1; then
        echo " — OK"
        break
    fi
    echo -n "."
    sleep 1
done

# === Bot ===
nohup .venv/bin/python bot/main.py > "$LOG_DIR/bot.log" 2>&1 &
BOT_PID=$!
echo "$BOT_PID" > "$RUN_DIR/bot.pid"
echo "[start] Bot PID: $BOT_PID  (лог: $LOG_DIR/bot.log)"

echo ""
echo "✅ Всё запущено."
echo "   • Backend:  http://127.0.0.1:8005/api/v1/health"
echo "   • Логи:     tail -f $LOG_DIR/backend.log $LOG_DIR/bot.log"
echo "   • Стоп:     ./stop-all.sh"
