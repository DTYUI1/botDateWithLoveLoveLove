FROM python:3.11-slim

WORKDIR /app

# Копирование requirements
COPY requirements.txt .

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода backend
COPY . .

# Запуск backend API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
