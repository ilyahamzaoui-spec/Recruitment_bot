# core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    # Токен для Ботов Telegram
    BOT_TOKEN_WELCOME: str
    BOT_TOKEN_RECRUITER: str

    # URL для подключения к PostgreSQL (пример: postgresql+asyncpg://user:pass@host/db)
    DATABASE_URL: str

    # ID Telegram-канала (например, @your_channel_name)
    CHANNEL_USERNAME: str

    # Список Telegram ID администраторов
    ADMIN_IDS: List[int] = []

    QC_CHAT_ID: int

    RECRUITING_API_URL: str

    # Настройка pydantic для чтения из .env файла
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


# Инициализация настроек
settings = Settings()