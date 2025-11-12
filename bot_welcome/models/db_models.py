# bot_welcome/models/db_models.py
from sqlalchemy import Column, Integer, Text, Boolean, TIMESTAMP, JSON, String, BigInteger
from datetime import datetime
from core.db import Base
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum

class ApplicationStatus(enum.Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    INVITED = "INVITED"
    REJECTED = "REJECTED"


class WelcomeContent(Base):
    __tablename__ = "welcome_content"

    id = Column(Integer, primary_key=True)
    welcome_text = Column(Text, nullable=False)
    links_json = Column(JSON, nullable=False)  # [{"title": "GitHub", "url": "..."}]
    last_updated = Column(TIMESTAMP, default=datetime.utcnow)


class CachedVacancy(Base):
    __tablename__ = "cached_vacancies"

    id = Column(Integer, primary_key=True)
    vacancy_title = Column(Text, nullable=False)
    telegram_link = Column(Text, nullable=False)
    post_id = Column(Integer, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)


class RecruiterMapping(Base):
    __tablename__ = "recruiters_mapping"

    direction = Column(String(50), primary_key=True)
    recruiter_tg_id = Column(BigInteger, nullable=False)
    recruiter_username = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    candidate_tg_id = Column(BigInteger, nullable=False)
    candidate_data = Column(JSON, nullable=True)
    vacancy_id = Column(Integer, nullable=False)
    vacancy_title = Column(Text, nullable=False)

    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.NEW, nullable=False)
    recruiter_id = Column(BigInteger, nullable=True)

    external_api_id = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    temp_fsm_data = Column(JSON, nullable=True)


class StatusUpdate(Base):
    __tablename__ = "status_updates"

    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    old_status = Column(Enum(ApplicationStatus), nullable=False)
    new_status = Column(Enum(ApplicationStatus), nullable=False)
    recruiter_id = Column(BigInteger, nullable=True)
    timestamp = Column(TIMESTAMP, default=datetime.utcnow)

    application = relationship("Application")
