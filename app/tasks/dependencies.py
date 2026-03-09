from typing import Generator, Optional
from sqlalchemy.orm import Session

from app.tasks.database import get_db as get_db_dep
from app.tasks.service import QuestService, SubtaskService


def get_db() -> Generator[Optional[Session], None, None]:
    """Dependency wrapper: возвращает SQLAlchemy Session или None (если включён Firestore)."""
    yield from get_db_dep()


def get_quest_service(db: Optional[Session] = None) -> QuestService:
    """Dependency для получения сервиса квестов"""
    if db is None:
        # вызов get_db_dep напрямую
        gen = get_db_dep()
        db = next(gen)
    return QuestService(db)


def get_subtask_service(db: Optional[Session] = None) -> SubtaskService:
    """Dependency для получения сервиса подзадач"""
    if db is None:
        gen = get_db_dep()
        db = next(gen)
    return SubtaskService(db)
