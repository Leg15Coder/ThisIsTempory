from typing import Generator
from sqlalchemy.orm import Session

from app.tasks.database import SessionLocal
from app.tasks.service import QuestService, SubtaskService


def get_db() -> Generator[Session, None, None]:
    """Dependency для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_quest_service(db: Session = None) -> QuestService:
    """Dependency для получения сервиса квестов"""
    if db is None:
        db = next(get_db())
    return QuestService(db)


def get_subtask_service(db: Session = None) -> SubtaskService:
    """Dependency для получения сервиса подзадач"""
    if db is None:
        db = next(get_db())
    return SubtaskService(db)
