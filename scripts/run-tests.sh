#!/bin/bash
# ConnectMe Test Runner Script
# Запуск всех тестов

set -e

echo "🧪 Running ConnectMe tests..."
echo "=============================="
echo ""

# Перейти в папку теста
cd "$(dirname "$0")/../test"

# Проверить что pytest установлен
if ! command -v pytest &> /dev/null; then
    echo "📦 Installing test dependencies..."
    pip install -r requirements.txt
fi

# Запустить тесты
echo "🚀 Running pytest..."
pytest -v --tb=short --color=yes "$@"

echo ""
echo "=============================="
echo "✅ Tests completed!"
