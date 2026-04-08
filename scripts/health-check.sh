#!/bin/bash
# ConnectMe Health Check Script
# Проверка здоровья всех сервисов

echo "🏥 ConnectMe Health Check"
echo "========================="
echo ""

EXIT_CODE=0

# ============================================
# DOCKER CONTAINERS
# ============================================
echo "🐳 Docker Containers:"
echo "---------------------"

containers=("connectme-postgres" "connectme-redis" "connectme-rabbitmq" "connectme-minio")

for container in "${containers[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "✅ ${container}: running"
    else
        echo "❌ ${container}: not running"
        EXIT_CODE=1
    fi
done

echo ""

# ============================================
# POSTGRESQL
# ============================================
echo "🗄️  PostgreSQL:"
echo "---------------"
if docker exec connectme-postgres pg_isready -U ${POSTGRES_USER:-connectme_user} -d ${POSTGRES_DB:-connectme_db} &> /dev/null; then
    echo "✅ PostgreSQL: healthy"
    
    # Проверить количество таблиц
    TABLE_COUNT=$(docker exec connectme-postgres psql -U ${POSTGRES_USER:-connectme_user} -d ${POSTGRES_DB:-connectme_db} -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
    if [ ! -z "$TABLE_COUNT" ]; then
        echo "   Tables: $TABLE_COUNT"
    fi
else
    echo "❌ PostgreSQL: unhealthy"
    EXIT_CODE=1
fi

echo ""

# ============================================
# REDIS
# ============================================
echo "💾 Redis:"
echo "---------"
if docker exec connectme-redis redis-cli ping | grep -q PONG; then
    echo "✅ Redis: healthy"
    
    # Проверить использование памяти
    MEMORY=$(docker exec connectme-redis redis-cli INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
    echo "   Memory: $MEMORY"
    
    # Проверить количество ключей
    KEYS=$(docker exec connectme-redis redis-cli DBSIZE | cut -d' ' -f2)
    echo "   Keys: $KEYS"
else
    echo "❌ Redis: unhealthy"
    EXIT_CODE=1
fi

echo ""

# ============================================
# RABBITMQ
# ============================================
echo "🐰 RabbitMQ:"
echo "------------"
if docker exec connectme-rabbitmq rabbitmq-diagnostics ping &> /dev/null; then
    echo "✅ RabbitMQ: healthy"
    
    # Проверить очереди
    QUEUES=$(docker exec connectme-rabbitmq rabbitmqctl list_queues name messages 2>/dev/null | tail -n +2)
    if [ ! -z "$QUEUES" ]; then
        echo "   Queues:"
        echo "$QUEUES" | while read -r line; do
            echo "     - $line"
        done
    fi
else
    echo "❌ RabbitMQ: unhealthy"
    EXIT_CODE=1
fi

echo ""

# ============================================
# MINIO
# ============================================
echo "📦 MinIO:"
echo "---------"
if curl -f http://localhost:9000/minio/health/live &> /dev/null; then
    echo "✅ MinIO: healthy"
    
    # Проверить buckets
    echo "   Console: http://localhost:9001"
else
    echo "❌ MinIO: unhealthy"
    EXIT_CODE=1
fi

echo ""

# ============================================
# BACKEND API (если запущен)
# ============================================
echo "🔌 Backend API:"
echo "---------------"
if curl -f http://localhost:8005/api/v1/health &> /dev/null; then
    echo "✅ Backend API: healthy"
else
    echo "⚠️  Backend API: not running (optional)"
fi

echo ""

# ============================================
# ИТОГО
# ============================================
echo "========================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All services are healthy!"
else
    echo "❌ Some services are unhealthy!"
    echo "   Run: ./scripts/setup-infra.sh to restart"
fi
echo ""

exit $EXIT_CODE
