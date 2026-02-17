from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.tasks.database import Base


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)  # Null для Google OAuth

    # Профиль
    display_name = Column(String, default="")
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)

    # Firebase UID для интеграции
    firebase_uid = Column(String, unique=True, index=True, nullable=True)

    # OAuth провайдеры
    google_id = Column(String, unique=True, index=True, nullable=True)

    # Статус
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Настройки
    theme = Column(String, default="dark")
    language = Column(String, default="ru")
    notifications_enabled = Column(Boolean, default=True)

    currency = Column(Integer, default=0)

    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    quests = relationship("Quest", back_populates="user", cascade="all, delete-orphan")
    quest_templates = relationship("QuestTemplate", back_populates="user", cascade="all, delete-orphan")
    shop_items = relationship("ShopItem", back_populates="user", cascade="all, delete-orphan")
    inventory_items = relationship("Inventory", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"


class RefreshToken(Base):
    """Модель для refresh токенов"""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True, nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_revoked = Column(Boolean, default=False)

    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken user_id={self.user_id}>"


class EmailVerification(Base):
    """Таблица для email verification токенов"""
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="email_verification")

    def __repr__(self):
        return f"<EmailVerification user_id={self.user_id} token={self.token}>"
