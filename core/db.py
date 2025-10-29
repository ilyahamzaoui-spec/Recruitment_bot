# core/db.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

# Базовый класс для всех ORM-моделей
class Base(DeclarativeBase):
    pass

# Асинхронный движок
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False # Установите True для логирования SQL-запросов
)

# Асинхронный класс фабрики сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession
)

async def init_db():
    """Создает таблицы, если они не существуют."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)