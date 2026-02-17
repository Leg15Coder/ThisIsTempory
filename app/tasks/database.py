from datetime import datetime, timedelta as dl

from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy import create_engine, Boolean, Float, ForeignKey
from sqlalchemy import Column, Integer, String, DateTime, Text, Table
import enum
import os
from dotenv import load_dotenv

load_dotenv()

USE_FIRESTORE = os.environ.get('FIRESTORE_ENABLED', '0') in ('1', 'true', 'True')
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

Base = declarative_base()

if USE_FIRESTORE:
    print('ℹ️ FIRESTORE_ENABLED detected in environment — пропускаем инициализацию SQLAlchemy (используется Firestore в проде)')
    engine = None
    SessionLocal = None

else:
    if not DATABASE_URL:
        DATABASE_URL = "sqlite:///./quests.db"

    _engine = None
    try:
        _connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
        _engine = create_engine(
            DATABASE_URL,
            connect_args=_connect_args,
            pool_pre_ping=True,
            echo=False
        )
    except Exception as e:
        print('⚠️ Ошибка при создании engine с DATABASE_URL=', DATABASE_URL, ' — ', e)
        if 'sqlite' in (DATABASE_URL or ''):
            print('⚠️ Переходим на in-memory SQLite в качестве fallback')
            _engine = create_engine(
                'sqlite:///:memory:',
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
                echo=False
            )
        else:
            raise

    engine = _engine

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    if USE_FIRESTORE:
        yield None
        return
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

    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    user = relationship("User", back_populates="quests")

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
        if not self.parents:
            return True

        return all(parent.status == QuestStatus.finished for parent in self.parents)

    def update_children_status(self):
        """Обновляет статусы дочерних квестов при изменении статуса родителя"""
        if self.status == QuestStatus.finished:
            for child in self.children:
                if child.status == QuestStatus.inactive and child.is_active:
                    child.status = QuestStatus.active

    def __str__(self):
        return f"<Quest {self.id}: {self.title} by {self.author}>"

    def __repr__(self):
        return f"<Quest {self.id}: {self.title} by {self.author}>"


class RecurrenceType(str, enum.Enum):
    """Тип периодичности для повторяющихся квестов"""
    daily = "daily"  # Ежедневно
    weekly = "weekly"  # Еженедельно (по дням недели)
    interval = "interval"  # Через фиксированный интервал


class QuestTemplate(Base):
    """Шаблон для периодически создаваемых квестов"""
    __tablename__ = "quest_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    title = Column(String, nullable=False)
    author = Column(String, default="???")
    description = Column(Text)
    cost = Column(Integer, nullable=False)
    rarity = Column(quest_rarity_enum, default=QuestRarity.common)
    scope = Column(String)

    recurrence_type = Column(String, nullable=False)  # daily/weekly/interval
    duration_hours = Column(Integer, nullable=False, default=24)  # Длительность квеста в часах

    weekdays = Column(String, nullable=True)

    interval_hours = Column(Integer, nullable=True)

    is_active = Column(Boolean, default=True)
    last_generated = Column(DateTime, nullable=True)
    start_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="quest_templates")

    def should_generate(self, now: datetime = None) -> bool:
        """Проверяет, нужно ли создать новый квест по этому шаблону"""
        if not self.is_active:
            return False

        if now is None:
            now = datetime.now()

        if self.start_at and now < self.start_at:
            return False

        # Если указан end_at — больше не генерируем
        if self.end_at and now > self.end_at:
            return False

        start_time = self.start_at.time() if self.start_at else None

        # DAILY
        if self.recurrence_type == RecurrenceType.daily.value:
            # не генерировать раньше времени запуска в день
            if start_time and now.time() < start_time:
                return False
            if self.last_generated is None:
                return True
            return now.date() > self.last_generated.date()

        # WEEKLY
        elif self.recurrence_type == RecurrenceType.weekly.value:
            if not self.weekdays:
                return False

            current_weekday = now.weekday()  # 0=пн, 6=вс
            target_weekdays = [int(d) for d in self.weekdays.split(',')]

            if current_weekday not in target_weekdays:
                return False

            if start_time and now.time() < start_time:
                return False

            if self.last_generated is None:
                return True

            # если уже генерили сегодня — не генерируем снова
            if self.last_generated.date() == now.date():
                return False

            return True

        # INTERVAL
        elif self.recurrence_type == RecurrenceType.interval.value:
            if not self.interval_hours:
                return False

            if self.last_generated is None:
                # Если ещё не генерировали, разрешим генерацию (при условии start_at уже проверено выше)
                return True
            elapsed = (now - self.last_generated).total_seconds() / 3600
            return elapsed >= self.interval_hours

        return False

    def generate_quest(self, db: Session) -> Quest:
        """Создаёт новый квест на основе шаблона"""
        now = datetime.now()
        deadline = now + dl(hours=self.duration_hours)

        new_quest = Quest(
            user_id=self.user_id,
            title=self.title,
            author=self.author,
            description=self.description,
            cost=self.cost,
            rarity=self.rarity,
            status=QuestStatus.active,
            scope=self.scope,
            created=now,
            deadline=deadline,
            is_new=True
        )

        db.add(new_quest)
        self.last_generated = now
        db.commit()
        db.refresh(new_quest)

        return new_quest


class ItemRarity(str, enum.Enum):
    """Редкость предмета"""
    common = "Обычный"
    uncommon = "Необычный"
    rare = "Редкий"
    epic = "Эпический"
    legendary = "Легендарный"


item_rarity_enum = ENUM(ItemRarity, name="itemrarity")


class ShopItem(Base):
    """Предмет в магазине"""
    __tablename__ = "shop_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Integer, nullable=False)  # Цена в валюте квестов
    rarity = Column(item_rarity_enum, default=ItemRarity.common)
    icon = Column(String, nullable=True)  # Emoji или URL картинки

    is_available = Column(Boolean, default=True)  # Доступен ли для покупки
    stock = Column(Integer, nullable=True)  # Количество (None = бесконечно)

    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="shop_items")

    def __repr__(self):
        return f"<ShopItem {self.name} ({self.price} монет)>"


class Inventory(Base):
    """Инвентарь пользователя (купленные предметы)"""
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    shop_item_id = Column(Integer, ForeignKey('shop_items.id'), nullable=False)

    quantity = Column(Integer, default=1)  # Количество купленных
    used_quantity = Column(Integer, default=0)  # Сколько использовано

    purchased_at = Column(DateTime, default=datetime.now)
    last_used = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="inventory_items")
    shop_item = relationship("ShopItem", backref="inventory_entries")

    @property
    def available_quantity(self):
        """Доступное количество (не использованное)"""
        return self.quantity - self.used_quantity

    def __repr__(self):
        return f"<Inventory user={self.user_id} item={self.shop_item_id} qty={self.available_quantity}>"


class QuestGenerator(Base):
    __tablename__ = "quest_generators"
    id = Column(Integer, primary_key=True, index=True)
    quest_id = Column(Integer, ForeignKey('quests.id'), nullable=False, index=True)
    quest = relationship("Quest", backref="generator")
    period = Column(DateTime, nullable=False)
    last_generate = Column(DateTime, nullable=False, default=datetime.now())

    def generate_quest(self):
        """Генерирует новый квест на основе шаблона (устаревший метод)"""
        db = Session.object_session(self)
        if not db:
            return

        created = datetime.now()

        if self.quest.deadline and self.quest.created:
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

        db.add(new_quest)
        db.commit()


def ensure_db_migrations():
    """Простейшие миграции для sqlite базы: добавляет колонку `currency` в users и создаёт таблицы магазина/инвентаря/шаблонов при необходимости."""
    from pathlib import Path
    import sqlite3
    if not DATABASE_URL.startswith('sqlite'):
        return

    db_path = DATABASE_URL.replace('sqlite:///', '')
    db_file = Path(db_path)
    if not db_file.exists():
        return

    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    try:
        try:
            cols = [c[1] for c in cur.execute("PRAGMA table_info('users')").fetchall()]
        except Exception:
            cols = []

        if 'currency' not in cols:
            try:
                cur.execute("ALTER TABLE users ADD COLUMN currency INTEGER DEFAULT 0")
                conn.commit()
            except Exception:
                pass

        # shop_items
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shop_items'")
        if not cur.fetchone():
            cur.execute('''
                CREATE TABLE shop_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    price INTEGER NOT NULL,
                    rarity TEXT DEFAULT 'Обычный',
                    icon TEXT,
                    is_available INTEGER DEFAULT 1,
                    stock INTEGER,
                    created_at TEXT DEFAULT (datetime('now'))
                );
            ''')
            cur.execute("CREATE INDEX IF NOT EXISTS ix_shop_items_user_id ON shop_items (user_id);")
            conn.commit()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory'")
        if not cur.fetchone():
            cur.execute('''
                CREATE TABLE inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    shop_item_id INTEGER NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    used_quantity INTEGER DEFAULT 0,
                    purchased_at TEXT DEFAULT (datetime('now')),
                    last_used TEXT
                );
            ''')
            cur.execute("CREATE INDEX IF NOT EXISTS ix_inventory_user_id ON inventory (user_id);")
            conn.commit()

        # quest_templates
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quest_templates'")
        if not cur.fetchone():
            cur.execute('''
                CREATE TABLE quest_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT DEFAULT '???',
                    description TEXT,
                    cost INTEGER NOT NULL,
                    rarity TEXT DEFAULT 'Обычный',
                    scope TEXT,
                    recurrence_type TEXT NOT NULL,
                    duration_hours INTEGER NOT NULL DEFAULT 24,
                    weekdays TEXT,
                    interval_hours INTEGER,
                    is_active INTEGER DEFAULT 1,
                    last_generated TEXT,
                    start_at TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
            ''')
            cur.execute("CREATE INDEX IF NOT EXISTS ix_quest_templates_user_id ON quest_templates (user_id);")
            conn.commit()
        else:
            # добавляем колонку start_at/end_at, если нет
            try:
                cols = [c[1] for c in cur.execute("PRAGMA table_info('quest_templates')").fetchall()]
            except Exception:
                cols = []
            if 'start_at' not in cols:
                try:
                    cur.execute("ALTER TABLE quest_templates ADD COLUMN start_at TEXT")
                    conn.commit()
                except Exception:
                    pass
            if 'end_at' not in cols:
                try:
                    cur.execute("ALTER TABLE quest_templates ADD COLUMN end_at TEXT")
                    conn.commit()
                except Exception:
                    pass

    finally:
        conn.close()


try:
    import app.auth.models  # noqa: F401
except Exception as e:
    print('⚠️ Не удалось импортировать app.auth.models при создании таблиц:', e)
print('✅ Модели загружены в metadata (проверка завершена)')
