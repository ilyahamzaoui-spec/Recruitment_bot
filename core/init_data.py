import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from bot_welcome.services.content_service import ContentService
from bot_welcome.services.application_service import ApplicationService
from core.config import settings
import logging

logging.basicConfig(level=logging.INFO)

async def insert_initial_data(session: AsyncSession):
    app_service = ApplicationService(session)
    content_service = ContentService(session)

    python_recruiter = await app_service.get_recruiter_by_direction('python')
    if not python_recruiter:
        await app_service.add_update_recruiter(
            direction='python',
            tg_id=settings.ADMIN_IDS[0],
            username='ilya_hamza'
        )
        logging.info("Inserted Python recruiter mapping.")

    if not await app_service.get_recruiter_by_direction('java'):
        await app_service.add_update_recruiter(
            direction='java',
            tg_id=8888888888,
            username='java_recruiter'
        )
        logging.info("Inserted Java recruiter mapping.")

    latest_vacancies = await content_service.get_latest_vacancies(limit=1)

    if not latest_vacancies:
        await content_service.add_vacancy_to_cache(
            title="Python Backend Developer",
            link='https://t.me/inno_recruiting/101',
            post_id=101,
            direction='python'
        )
        await content_service.add_vacancy_to_cache(
            title='Senior Java Engineer',
            link='https://t.me/inno_recruiting/102',
            post_id=102,
            direction='java'
        )
        logging.info("Inserted initial vacancy into cache.")

    await session.commit()