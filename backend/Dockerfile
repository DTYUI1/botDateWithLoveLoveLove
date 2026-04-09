FROM python:3.11-slim

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements
COPY backend/requirements.txt .

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода backend
COPY backend/ .

# Копирование shared infrastructure (redis cache patterns)
COPY infrastructure/ /app/infrastructure/

# Создание директории для логов
RUN mkdir -p logs

# Запуск backend API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
