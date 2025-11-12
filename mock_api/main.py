# mock_api/main.py
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import uuid
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(title="Mock Recruiting API", version="1.0.0")

# Временное хранилище данных (для простоты мока)
# {external_id: application_data}
mock_database: Dict[str, Dict[str, Any]] = {}


# --- Pydantic Модели ---
class CandidateContacts(BaseModel):
    phone: str
    email: str
    telegram_username: str
    tg_id: int


class ProfessionalInfo(BaseModel):
    level: str
    skills: str
    experience: str


class ApplicationCandidate(BaseModel):
    full_name: str
    contacts: CandidateContacts
    professional_info: ProfessionalInfo
    resume_link: str
    source: str = Field(default="telegram_bot")


class ApplicationCreate(BaseModel):
    vacancy_id: str = Field(..., description="ID вакансии из нашей системы (post_id)")
    candidate: ApplicationCandidate


class StatusUpdate(BaseModel):
    status: str = Field(..., description="Новый статус: new, in_progress, invited, rejected")
    recruiter_id: str = Field(..., description="Telegram ID рекрутера, обновившего статус")
    reason: Optional[str] = None


# --- Эндпоинты ---

@app.post("/api/applications", status_code=201)
async def create_application(app_data: ApplicationCreate):
    """Эндпоинт для создания новой заявки (отклик кандидата)."""
    external_id = str(uuid.uuid4())

    application_record = {
        "id": external_id,
        "status": "new",
        "vacancy_id": app_data.vacancy_id,
        "candidate": app_data.candidate.dict(),
        "created_at": datetime.utcnow().isoformat(),
        "history": [{"status": "new", "timestamp": datetime.utcnow().isoformat()}]
    }

    mock_database[external_id] = application_record

    logging.info(
        f"Mock API: Received new application for VACANCY {app_data.vacancy_id}. Assigned external ID: {external_id}")

    return {"id": external_id, "message": "Application created successfully."}


@app.patch("/api/applications/{app_id}/status", status_code=200)
async def update_application_status(app_id: str, status_update: StatusUpdate):
    """Эндпоинт для обновления статуса заявки (используется Recruiter Bot)."""
    if app_id not in mock_database:
        raise HTTPException(status_code=404, detail="Application not found in external system.")

    record = mock_database[app_id]

    new_status = status_update.status
    recruiter_id = status_update.recruiter_id
    reason = status_update.reason

    # Обновление записи
    record['status'] = new_status
    record['history'].append({
        "status": new_status,
        "recruiter_id": recruiter_id,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat()
    })

    logging.info(f"Mock API: Status updated for ID {app_id} to '{new_status}' by recruiter {recruiter_id}")

    return {"message": f"Status updated to {new_status}"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}