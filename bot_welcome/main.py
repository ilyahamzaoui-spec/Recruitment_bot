# bot_welcome/main.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage


from bot_welcome.handlers.user import user_router
from bot_welcome.handlers.admin import admin_router
from bot_welcome.middlewares.db_middleware import DBSessionMiddleware
from core.config import settings
from core.db import init_db, AsyncSessionLocal
from core.init_data import insert_initial_data

logging.basicConfig(level=logging.INFO)


async def main():
    # 1. Инициализация БД
    await init_db()

    async with AsyncSessionLocal() as session:
        await insert_initial_data(session)

    # 2. Инициализация Бота и Диспетчера
    bot = Bot(
        token=settings.CANDIDATE_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # 3. Регистрация Мидлвара (Dependency Injection)
    # Мидлвар будет создавать сессию и передавать её в хендлеры как аргумент 'session'
    db_middleware = DBSessionMiddleware(session_pool=AsyncSessionLocal)
    dp.update.outer_middleware(db_middleware)

    # 4. Регистрация роутеров
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # 5. Запуск бота
    logging.info("Starting User Bot ...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by KeyboardInterrupt.")