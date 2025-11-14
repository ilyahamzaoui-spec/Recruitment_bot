# bot_3_qc/main.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage


from core.config import settings
from core.db import AsyncSessionLocal # ИСПРАВЛЕНО
from bot_welcome.middlewares.db_middleware import DBSessionMiddleware # НОВЫЙ ИМПОРТ
from bot_3_qc.handlers.recruiter import recruiter_router

logging.basicConfig(level=logging.INFO)


async def main():
    logging.info("Starting Recruiter Bot for QC Chat...")

    # Инициализация Бота и Диспетчера
    # Используем токен рекрутера (который мы исправили в .env)
    bot = Bot(
        token=settings.RECRUITER_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)) # Используем V2 для QC-чата
    dp = Dispatcher(storage=MemoryStorage())

    # 1. Регистрация Мидлвара (Dependency Injection)
    # Используем уже определенный AsyncSessionLocal
    db_middleware = DBSessionMiddleware(session_pool=AsyncSessionLocal)
    dp.update.outer_middleware(db_middleware)

    # 2. Регистрация роутера
    dp.include_router(recruiter_router)

    # 3. Запуск бота
    logging.info(f"Recruiter Bot is listening to chat ID: {settings.QC_CHAT_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Recruiter Bot stopped by KeyboardInterrupt.")