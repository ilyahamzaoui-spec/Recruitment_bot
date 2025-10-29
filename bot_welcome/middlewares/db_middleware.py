# bot_welcome/middlewares/db_middleware.py
from typing import Callable, Awaitable, Any, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

class DBSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # 1. Создаем сессию
        async with self.session_pool() as session:
            # 2. Инжектируем сессию в контекст данных (data)
            data["session"] = session
            # 3. Вызываем следующий хендлер/мидлвар
            return await handler(event, data)
        # Сессия автоматически закрывается при выходе из with-блока