from datetime import datetime, timedelta as dl

from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy import create_engine, Boolean, Float, ForeignKey
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, Table
import enum
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./quests.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    inactive = "Неактивный"
    abstract = "Абстрактный"


class SubtaskType(str, enum.Enum):
    checkbox = 'checkbox'
    numeric = 'numeric'


quest_rarity_enum = ENUM(QuestRarity, name="questrarity")
quest_status_enum = ENUM(QuestStatus, name="queststatus")
subtask_type_enum = ENUM(SubtaskType, name="subtasktype")


class SubtaskBase(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text, nullable=False)
    weight = Column(Integer, default=1, nullable=False)
    type = Column(subtask_type_enum, default=SubtaskType.checkbox, nullable=False)
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


quest_relationship = Table(
    'quest_relationships', Base.metadata,
    Column('parent_id', Integer, ForeignKey('quests.id'), primary_key=True),
    Column('child_id', Integer, ForeignKey('quests.id'), primary_key=True)
)


class Quest(Base):
    __tablename__ = "quests"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    author = Column(String, default="???")
    description = Column(Text)
    cost = Column(Integer, nullable=False)
    deadline = Column(DateTime)
    created = Column(DateTime)
    rarity = Column(quest_rarity_enum, default=QuestRarity.common)
    status = Column(quest_status_enum, default=QuestStatus.inactive)
    scope = Column(String)
    is_new = Column(Boolean, default=True)

    children = relationship(
        "Quest",
        secondary=quest_relationship,
        primaryjoin=(id == quest_relationship.c.parent_id),
        secondaryjoin=(id == quest_relationship.c.child_id),
        backref="parents",
        lazy='selectin'
    )

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

    @property
    def is_active(self):
        """Проверяет, должен ли квест быть активным"""
        # Если нет родителей - квест активен по умолчанию
        if not self.parents:
            return True

        # Проверяем, все ли родительские квесты завершены успешно
        return all(parent.status == QuestStatus.finished for parent in self.parents)

    async def update_status(self):
        """Обновляет статус квеста на основе прогресса и родительских квестов"""
        db = Session.object_session(self)

        if self.is_active and self.status == QuestStatus.inactive:
            self.status = QuestStatus.active

        # Проверяем условия завершения
        if (self.status == QuestStatus.active and self.progress == 100
                or self.status in (QuestStatus.finished, QuestStatus.failed)):
            # self.status = QuestStatus.finished
            # Активируем дочерние квесты
            for child in self.children:
                await child.update_status()

        if db:
            db.commit()

    def __str__(self):
        return f"<Quest {self.id}: {self.title} by {self.author}>"

    def __repr__(self):
        return f"<Quest {self.id}: {self.title} by {self.author}>"


class QuestGenerator(Base):
    __tablename__ = "quest_generators"
    id = Column(Integer, primary_key=True, index=True)
    quest_id = Column(Integer, ForeignKey('quests.id'), nullable=False, index=True)
    quest = relationship("Quest", backref="generator")
    period = Column(DateTime, nullable=False)
    last_generate = Column(DateTime, nullable=False, default=datetime.now())

    def generate_quest(self):
        if self.quest.deadline:
            db = Session.object_session(self)

            created = datetime.now()
            if self.quest.created:
                delta = self.quest.deadline - self.quest.created
            else:
                delta = dl(days=1)

            new_quest = Quest(
                title=self.quest.title,
                author=self.quest.author,
                description=self.quest.description,
                cost=self.quest.cost,
                created=created,
                deadline=created + delta,
                rarity=self.quest.rarity,
                status=QuestStatus.active,
                is_new=True
            )

            if db:
                db.add(new_quest)
                db.commit()


Base.metadata.create_all(bind=engine)
