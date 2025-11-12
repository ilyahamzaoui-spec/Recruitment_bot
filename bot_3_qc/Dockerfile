# bot_welcome/Dockerfile
# Используем официальный базовый образ Python (slim версия для уменьшения размера)
FROM python:3.12-slim

# Устанавливаем необходимые зависимости для asyncpg и PostgreSQL
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc && \
    rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь исходный код приложения
COPY . .

# CMD - не нужен, так как он переопределяется в docker-compose.yml