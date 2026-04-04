#!/bin/bash
# Запуск ConnectMe бота и backend
set -e

cd /home/artwox/orchestrAI/loveBot/projects/connectme

export PYTHONPATH=.
export HTTP_PROXY="http://127.0.0.1:7897"
export HTTPS_PROXY="http://127.0.0.1:7897"
export ALL_PROXY="http://127.0.0.1:7897"
export http_proxy="$HTTP_PROXY"
export https_proxy="$HTTPS_PROXY"
export all_proxy="$ALL_PROXY"

# Backend
cd backend
DATABASE_URL="postgresql+asyncpg://connectme_user:connectme_secure_pass@127.0.0.1:5432/connectme_db" \
REDIS_URL="redis://127.0.0.1:6379/0" \
RABBITMQ_URL="amqp://guest:guest@127.0.0.1:5672//" \
../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8005 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
sleep 5

# Bot
cd ..
.venv/bin/python bot/main.py &
BOT_PID=$!
echo "Bot PID: $BOT_PID"

# Ждём
wait
