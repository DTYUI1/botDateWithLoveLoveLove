#!/bin/bash
# Production deploy для ConnectMe.
# Идемпотентный pull → build → up → health-check.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f .env ]; then
    echo "❌ Файл .env не найден. Скопируйте .env.example → .env и заполните секреты."
    exit 1
fi

echo "📥 Pull последних изменений…"
git pull --ff-only || echo "⚠️ git pull пропущен (нет remote или нечего тянуть)"

echo "🛠️ Сборка образов…"
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

echo "🚀 Запуск стека…"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo "⏳ Ожидание готовности backend…"
for i in {1..30}; do
    if curl -fsS http://localhost/api/v1/health >/dev/null 2>&1; then
        echo "✅ Backend здоров"
        break
    fi
    sleep 2
done

echo ""
echo "📊 Статус контейнеров:"
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

echo ""
echo "🌐 URL-ы:"
echo "  API:        http://localhost/api/v1/health"
echo "  Grafana:    http://localhost:3000  (admin / \$GRAFANA_ADMIN_PASSWORD)"
echo "  Prometheus: http://localhost:9090"
echo "  RabbitMQ:   http://localhost:15672"
echo "  MinIO:      http://localhost:9001"
