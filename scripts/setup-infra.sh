#!/bin/bash
# ConnectMe Infrastructure Setup Script
# Полная установка и проверка инфраструктуры

set -e

echo "🚀 Setting up ConnectMe infrastructure..."
echo "=========================================="

# ============================================
# ПРОВЕРКА DOCKER
# ============================================
echo ""
echo "📦 Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    echo "   Установите Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose не установлен!"
    echo "   Установите Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker is available"

# ============================================
# СОЗДАНИЕ .ENV
# ============================================
echo ""
echo "📝 Checking .env file..."
if [ ! -f .env ]; then
    echo "⚠️  .env не найден, создаём из .env.example..."
    cp .env.example .env
    echo "✅ .env создан"
    echo "⚠️  ВАЖНО: Обновите пароли в .env файле!"
else
    echo "✅ .env уже существует"
fi

# ============================================
# ЗАПУСК ИНФРАСТРУКТУРЫ
# ============================================
echo ""
echo "🐳 Starting infrastructure services..."
docker compose -f docker-compose.infra.yml up -d

echo "⏳ Waiting for services to start..."
sleep 10

# ============================================
# ПРОВЕРКА ЗДОРОВЬЯ
# ============================================
echo ""
echo "🏥 Checking service health..."

# PostgreSQL
if docker exec connectme-postgres pg_isready -U ${POSTGRES_USER:-connectme_user} -d ${POSTGRES_DB:-connectme_db} &> /dev/null; then
    echo "✅ PostgreSQL: healthy"
else
    echo "❌ PostgreSQL: unhealthy"
fi

# Redis
if docker exec connectme-redis redis-cli ping | grep -q PONG; then
    echo "✅ Redis: healthy"
else
    echo "❌ Redis: unhealthy"
fi

# RabbitMQ
if docker exec connectme-rabbitmq rabbitmq-diagnostics ping &> /dev/null; then
    echo "✅ RabbitMQ: healthy"
else
    echo "❌ RabbitMQ: unhealthy"
fi

# MinIO
if curl -f http://localhost:9000/minio/health/live &> /dev/null; then
    echo "✅ MinIO: healthy"
else
    echo "❌ MinIO: unhealthy"
fi

# ============================================
# НАСТРОЙКА MINIO
# ============================================
echo ""
echo "📁 Setting up MinIO buckets..."
if [ -f infrastructure/minio/setup.sh ]; then
    chmod +x infrastructure/minio/setup.sh
    # Запустить setup внутри контейнера MinIO
    docker exec connectme-minio sh -c "
        mc alias set myminio http://localhost:9000 ${MINIO_ACCESS_KEY:-minioadmin} ${MINIO_SECRET_KEY:-minioadmin} && \
        mc mb myminio/profile-photos --ignore-existing && \
        mc anonymous set none myminio/profile-photos
    " || echo "⚠️  MinIO setup failed, continuing..."
    echo "✅ MinIO setup completed"
fi

# ============================================
# ИТОГО
# ============================================
echo ""
echo "=========================================="
echo "✅ Infrastructure setup completed!"
echo ""
echo "📊 Access services:"
echo "   PostgreSQL: localhost:5432"
echo "   Redis: localhost:6379"
echo "   RabbitMQ Management: http://localhost:15672 (guest/guest)"
echo "   MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
echo ""
echo "🎯 Next steps:"
echo "   1. Run tests: cd test && pytest"
echo "   2. Start backend: cd backend && uvicorn main:app --reload"
echo "   3. Start bot: cd bot && python main.py"
echo "=========================================="
