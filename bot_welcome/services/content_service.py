# bot_welcome/services/content_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from bot_welcome.models.db_models import WelcomeContent, CachedVacancy
from typing import List, Dict, Any, Optional
from datetime import datetime


class ContentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Чтение данных ---

    async def get_welcome_data(self) -> tuple[str, List[Dict[str, str]]]:
        """Получает текущий текст приветствия и ссылки."""
        result = await self.session.execute(
            select(WelcomeContent).order_by(WelcomeContent.id.desc()).limit(1)
        )
        content: WelcomeContent = result.scalars().first()
        if content:
            return content.welcome_text, content.links_json
        return "Привет! Используйте /help для справки.", []

    async def get_latest_vacancies(self, limit: int = 5) -> List[CachedVacancy]:
        """Получает N последних активных вакансий."""
        result = await self.session.execute(
            select(CachedVacancy)
            .where(CachedVacancy.is_active == True)
            .order_by(CachedVacancy.post_id.desc())
            .limit(limit)
        )
        return result.scalars().all()

    def format_vacancies_text(self, vacancies: List[CachedVacancy]) -> str:
        """Форматирует список вакансий для сообщения в Markdown."""
        if not vacancies:
            return "Актуальных вакансий пока нет."

        text = "**🔥 Горячие Вакансии:**\n"
        for i, vacancy in enumerate(vacancies, 1):
            # [Название](ссылка) для кликабельности
            text += f"{i}. [{vacancy.vacancy_title}]({vacancy.telegram_link})\n"

        return text

    # --- Администрирование ---

    async def update_welcome_content(self, text: str, links: List[Dict[str, str]]):
        """Обновляет шаблон приветствия и ссылки."""
        new_content = WelcomeContent(
            welcome_text=text,
            links_json=links,
            last_updated=datetime.utcnow()
        )
        self.session.add(new_content)
        await self.session.commit()

    async def add_vacancy_to_cache(self, title: str, link: str, post_id: int) -> bool:
        """Добавляет или обновляет вакансию в кэше."""
        # Проверяем на дубликат по post_id
        exists = await self.session.execute(
            select(CachedVacancy).where(CachedVacancy.post_id == post_id)
        )
        if exists.scalar_one_or_none():
            return False

        new_vacancy = CachedVacancy(
            vacancy_title=title,
            telegram_link=link,
            post_id=post_id,
            is_active=True
        )
        self.session.add(new_vacancy)
        await self.session.commit()
        return True

    async def toggle_vacancy_active(self, post_id: int, is_active: bool):
        """Активирует/деактивирует вакансию по ID поста."""
        result = await self.session.execute(
            select(CachedVacancy).where(CachedVacancy.post_id == post_id)
        )
        vacancy = result.scalars().first()
        if vacancy:
            vacancy.is_active = is_active
            await self.session.commit()
            return True
        return False