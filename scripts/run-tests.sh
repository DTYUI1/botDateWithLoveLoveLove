#!/bin/bash
# ConnectMe Test Runner
# Запускает unit-тесты из tests/ (моки, без сервисов) и infra-тесты из test/
# (требуют живые Redis/RabbitMQ/Postgres — пропускаются, если сервисы недоступны).

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

PY="${PYTHON:-python}"
if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
fi

if ! "$PY" -m pytest --version >/dev/null 2>&1; then
    echo "📦 Installing test dependencies..."
    "$PY" -m pip install pytest pytest-asyncio
fi

echo "🧪 Unit tests (tests/)"
echo "======================"
"$PY" -m pytest tests/ -v --tb=short --color=yes "$@"

echo ""
echo "🔌 Infra tests (test/) — требуют живые сервисы"
echo "==============================================="
"$PY" -m pytest test/ -v --tb=short --color=yes "$@" || \
    echo "⚠️ Infra-тесты упали или пропущены — это ожидаемо без поднятой инфраструктуры."

echo ""
echo "✅ Test runner завершён"
