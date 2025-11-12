# bot_welcome/Dockerfile - ИСПРАВЛЕННЫЙ ВАРИАНТ
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Копируем ГЛАВНЫЙ requirements.txt (не mock_api) и устанавливаем
# Это предполагает, что requirements.txt находится в корне проекта (../requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Копируем все папки-модули, необходимые для работы бота
# Контекст сборки - корень проекта (..)
COPY bot_welcome /app/bot_welcome
COPY core /app/core
COPY bot_3_qc /app/bot_3_qc
COPY mock_api /app/mock_api

# CMD не нужен, так как переопределен в docker-compose.yml