from datetime import datetime

from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy import create_engine, Boolean, Float, ForeignKey
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


class SubtaskType(str, enum.Enum):
    checkbox = 'checkbox'
    numeric = 'numeric'


class SubtaskBase(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text, nullable=False)
    weight = Column(Integer, default=1, nullable=False)
    type = Column(Enum(SubtaskType), default=SubtaskType.checkbox, nullable=False)
    quest_id = Column(Integer, ForeignKey('quests.id'), nullable=False, index=True)

    def __init__(self, **kwargs):
        if 'type' not in kwargs:
            kwargs['type'] = self.__mapper_args__['polymorphic_identity']
        super().__init__(**kwargs)


class CheckboxSubtask(SubtaskBase):
    __tablename__ = "checkbox_subtasks"
    completed = Column(Boolean, default=False)
    __mapper_args__ = {
        'polymorphic_identity': SubtaskType.checkbox
    }


class NumericSubtask(SubtaskBase):
    __tablename__ = "numeric_subtasks"
    target = Column(Float, nullable=False)
    current = Column(Float, default=0)
    __mapper_args__ = {
        'polymorphic_identity': SubtaskType.numeric
    }


class Quest(Base):
    __tablename__ = "quests"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    author = Column(String, default="???")
    description = Column(Text)
    deadline = Column(DateTime)
    created = Column(DateTime)
    rarity = Column(Enum(QuestRarity), default=QuestRarity.common)
    status = Column(Enum(QuestStatus), default=QuestStatus.active)
    scope = Column(String)

    checkbox_subtasks = relationship(
        "CheckboxSubtask",
        backref="quest",
        cascade="all, delete-orphan",
        lazy='selectin'
    )

    numeric_subtasks = relationship(
        "NumericSubtask",
        backref="quest",
        cascade="all, delete-orphan",
        lazy='selectin'
    )

    @property
    def subtasks(self):
        """Объединяем подзадачи в одном списке для удобства"""
        return self.checkbox_subtasks + self.numeric_subtasks

    @property
    def progress(self):
        total_weight = 0
        completed_weight = 0

        for subtask in self.checkbox_subtasks:
            total_weight += subtask.weight
            if subtask.completed:
                completed_weight += subtask.weight

        for subtask in self.numeric_subtasks:
            total_weight += subtask.weight
            if subtask.current >= subtask.target:
                completed_weight += subtask.weight
            else:
                completed_weight += subtask.weight * (subtask.current / subtask.target)

        if total_weight > 0:
            return round((completed_weight / total_weight) * 100)
        return 0


Base.metadata.create_all(bind=engine)
