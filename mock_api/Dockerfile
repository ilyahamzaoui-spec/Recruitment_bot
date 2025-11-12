# mock_api/Dockerfile
FROM python:3.12-slim

# Устанавливаем необходимые системные зависимости для сборки (поскольку боты их используют)
# Хотя Mock API не использует asyncpg напрямую, мы используем тот же базовый образ
# и набор зависимостей для совместимости контекста сборки.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc && \
    rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# 1. Устанавливаем зависимости для Mock API (fastapi, uvicorn)
COPY mock_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Копируем сам код Mock API в /app/mock_api
RUN mkdir -p mock_api
COPY mock_api/main.py mock_api/

# 3. Копируем общие модули проекта, чтобы Mock API мог их импортировать
# (например, для Pydantic моделей, если бы мы их импортировали в main.py Mock API)
COPY core /app/core
COPY bot_welcome /app/bot_welcome
COPY bot_3_qc /app/bot_3_qc

# Команда запуска Uvicorn
# Uvicorn теперь сможет найти модуль 'mock_api.main' в PYTHONPATH
CMD ["uvicorn", "mock_api.main:app", "--host", "0.0.0.0", "--port", "8001"]