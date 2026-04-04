FROM python:3.11-slim

WORKDIR /app

# Копирование requirements
COPY requirements.txt .

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода бота
COPY . .

# Создание директории для логов
RUN mkdir -p logs

# Запуск бота
CMD ["python", "main.py"]
