from datetime import datetime

from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text
import enum


Base = declarative_base()
engine = create_engine("sqlite:///./quests.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class QuestRarity(str, enum.Enum):
    common = "Обычный"
    uncommon = "Необычный"
    rare = "Редкий"
    epic = "Эпический"
    legendary = "Легендарный"


class QuestStatus(str, enum.Enum):
    active = "Выполняется"
    finished = "Завершённый"
    failed = "Проваленный"


class Quest(Base):
    __tablename__ = "quests"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    author = Column(String, default="???")
    description = Column(Text)
    deadline = Column(DateTime)
    created = Column(DateTime, default=datetime.now())
    rarity = Column(Enum(QuestRarity), default=QuestRarity.common)
    status = Column(Enum(QuestStatus), default=QuestStatus.active)


Base.metadata.create_all(bind=engine)
