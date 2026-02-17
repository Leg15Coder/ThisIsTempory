from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRegister(BaseModel):
    """Схема для регистрации пользователя"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    username: Optional[str] = None
    display_name: Optional[str] = None


class UserLogin(BaseModel):
    """Схема для входа"""
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    """Схема для Google OAuth"""
    id_token: str


class FirebaseAuthRequest(BaseModel):
    """Схема для Firebase аутентификации"""
    firebase_token: str


class UserResponse(BaseModel):
    """Публичная информация о пользователе"""
    id: int
    email: str
    username: Optional[str]
    display_name: str
    avatar_url: Optional[str]
    bio: Optional[str]
    is_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Ответ с токенами"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserProfileUpdate(BaseModel):
    """Схема для обновления профиля"""
    display_name: Optional[str] = Field(None, max_length=100)
    username: Optional[str] = Field(None, max_length=50)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = None


class UserSettingsUpdate(BaseModel):
    """Схема для обновления настроек"""
    theme: Optional[str] = Field(None, pattern=r"^(light|dark)$")
    language: Optional[str] = Field(None, pattern=r"^(ru|en)$")
    notifications_enabled: Optional[bool] = None


class PasswordChange(BaseModel):
    """Схема для смены пароля"""
    current_password: str
    new_password: str = Field(..., min_length=8)
