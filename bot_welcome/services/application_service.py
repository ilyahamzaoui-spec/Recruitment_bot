import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from bot_welcome.models.db_models import RecruiterMapping, Application, ApplicationStatus, StatusUpdate
from core.config import settings
from typing import Dict, Any, Optional
import aiohttp
import json
from datetime import datetime

class ApplicationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.api_url = settings.RECRUITING_API_URL
        self.headers = {"Content-Type": "application/json"}

    async def get_recruiter_by_direction(self, direction: str) -> Optional[RecruiterMapping]:
        result = await self.session.execute(
            select(RecruiterMapping)
            .where(RecruiterMapping.direction == direction.lower())
            .where(RecruiterMapping.is_active == True)
        )
        return result.scalars().first()

    async def add_update_recruiter(self, direction:str, tg_id: int, username: str, is_active:bool = True):
        direction = direction.lower()
        recruiter = await self.session.get(RecruiterMapping, direction)

        if recruiter:
            recruiter.recruiter_tg_id = tg_id
            recruiter.recruiter_username = username
            recruiter.is_active = is_active
        else:
            recruiter = RecruiterMapping(
                direction=direction,
                recruiter_tg_id=tg_id,
                recruiter_username=username,
                is_active=is_active
            )
            self.session.add(recruiter)

        await self.session.commit()
        return True

    async def create_new_application(self, candidate_tg_id: int, vacancy_id: int, vacancy_title: str, temp_data: Dict[str, Any]) -> Application:
        application = Application(
            candidate_tg_id=candidate_tg_id,
            vacancy_id=vacancy_id,
            vacancy_title=vacancy_title,
            status=ApplicationStatus.NEW,
            temp_fsm_data=temp_data
        )
        self.session.add(application)
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def update_temp_data(self, application_id: int, temp_data: Dict[str, Any]) -> tuple[str, Any]:
        application = await self.session.get(Application, application_id)
        if application:
            application.temp_fsm_data = temp_data
            await self.session.commit()

    async def finalize_and_send_application(self, application_id: int, final_data: Dict[str, Any]) -> tuple[bool, str]:
        application = await self.session.get(Application, application_id)
        if not application:
            return False, "Application not found."

        payload = {
            "vacancy_id": str(application.vacancy_id), # Отправляем как строку
            "candidate": {
                "full_name": final_data.get('full_name'),
                "contacts": final_data.get('contacts'),
                "professional_info": final_data.get('professional_info'),
                "resume_link": final_data.get('resume_link'),
                "source": "telegram_bot"
            }
        }

        success = False
        external_id = None
        error_message = ""

        try:
            async with aiohttp.ClientSession() as client_session:
                async with client_session.post(f"{self.api_url}/api/applications", json=payload, headers=self.headers) as response:

                    if response.status == 201:
                        api_response = await response.json()
                        external_id = api_response.get('id')
                        success = True
                    else:
                        error_message = f"API Error: {response.status}: {await response.text()}"
        except aiohttp.ClientError as e:
            error_message = f"Network/Connection error: {e}"
        except json.JSONDecodeError:
            error_message = "Invalid JSON response from API."

        if success:
            application.candidate_data = final_data
            application.external_api_id = external_id
            application.temp_fsm_data = None
            await self.session.commit()
            return True, external_id
        else:
            application.temp_fsm_data = {"final_data": final_data, "error": error_message, "timestamp": str(datetime.utcnow())}
            await self.session.commit()
            return False, error_message

    async def update_application_status(self, application_id: int, new_status: ApplicationStatus, recruiter_tg_id: int, reason: Optional[str] = None) -> bool:
        application = await self.session.get(Application, application_id)
        if not application:
            return False

        old_status = application.status
        application.status = new_status
        application.recruiter_id = recruiter_tg_id
        await self.session.commit()

        status_log = StatusUpdate(
            application_id=application_id,
            old_status=old_status,
            new_status=new_status,
            recruiter_id=recruiter_tg_id,
            reason=reason,
            timestamp=datetime.utcnow()
        )
        self.session.add(status_log)
        await self.session.commit()
        payload = {
            "status": new_status.value.lower(),
            "recruiter_id": str(recruiter_tg_id),
            "reason": reason,
        }

        try:
            async with aiohttp.ClientSession() as client_session:
                async with client_session.patch(f"{self.api_url}/applications/{application.external_api_id}/status", json=payload, headers=self.headers) as response:
                    if response.status not in [200, 204]:
                        logging.error(f"Failed to update status in external API: {application.external_api_id}: {await response.text()}")
        except aiohttp.ClientError as e:
            logging.error(f"Network error updating API status for application {application_id}: {e}")

        return True
