from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.tasks.database import get_db
from app.auth.models import User
from app.auth.schemas import UserResponse, UserProfileUpdate, UserSettingsUpdate, PasswordChange
from app.auth.dependencies import require_user
from app.auth.security import verify_password, get_password_hash, validate_password
from app.core.fastapi_config import templates

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user: User = Depends(require_user)
):
    """Страница профиля"""
    return templates.TemplateResponse("auth/profile.html", {
        "request": request,
        "user": current_user,
        "base_url": "/quest-app"
    })


@router.get("/api", response_model=UserResponse)
async def get_profile(current_user: User = Depends(require_user)):
    """Получить данные профиля (API)"""
    return UserResponse.model_validate(current_user)


@router.put("/api", response_model=UserResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """Обновить профиль"""
    if profile_data.username and profile_data.username != current_user.username:
        existing = db.query(User).filter(
            User.username == profile_data.username,
            User.id != current_user.id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Это имя пользователя уже занято"
            )

    if profile_data.display_name is not None:
        current_user.display_name = profile_data.display_name

    if profile_data.username is not None:
        current_user.username = profile_data.username

    if profile_data.bio is not None:
        current_user.bio = profile_data.bio

    if profile_data.avatar_url is not None:
        current_user.avatar_url = profile_data.avatar_url

    db.commit()
    db.refresh(current_user)

    return UserResponse.model_validate(current_user)


@router.put("/settings", response_model=UserResponse)
async def update_settings(
    settings: UserSettingsUpdate,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """Обновить настройки аккаунта"""

    if settings.theme is not None:
        current_user.theme = settings.theme

    if settings.language is not None:
        current_user.language = settings.language

    if settings.notifications_enabled is not None:
        current_user.notifications_enabled = settings.notifications_enabled

    db.commit()
    db.refresh(current_user)

    return UserResponse.model_validate(current_user)


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """Смена пароля"""
    if not current_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы используете вход через Google. Смена пароля недоступна."
        )

    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль"
        )

    if not validate_password(password_data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Новый пароль должен содержать минимум 8 символов"
        )

    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()

    return {"message": "Пароль успешно изменён"}


@router.delete("/api")
async def delete_account(
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """Удалить аккаунт"""
    current_user.is_active = False
    db.commit()

    return {"message": "Аккаунт деактивирован"}
