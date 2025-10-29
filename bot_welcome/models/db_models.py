# bot_welcome/models/db_models.py
from sqlalchemy import Column, Integer, Text, Boolean, TIMESTAMP, JSON
from datetime import datetime
from core.db import Base  # Импортируем базовый класс


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