from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.tasks.database import get_db
from app.auth.models import User, RefreshToken, EmailVerification
from app.auth.schemas import (
    UserRegister, UserLogin, TokenResponse, UserResponse,
    GoogleAuthRequest, FirebaseAuthRequest
)
from app.auth.security import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, decode_token, validate_password
)
from app.auth.firebase_auth import firebase_service
from app.auth.dependencies import get_current_user, require_user
from app.core.fastapi_config import templates
from app.auth.mail_utils import send_verification_email
import secrets
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, current_user: User = Depends(get_current_user)):
    """Страница входа"""
    if current_user:
        return RedirectResponse(url="/quest-app", status_code=303)

    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "firebase_enabled": firebase_service.initialized
    })


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, current_user: User = Depends(get_current_user)):
    """Страница регистрации"""
    if current_user:
        return RedirectResponse(url="/quest-app", status_code=303)

    return templates.TemplateResponse("auth/register.html", {
        "request": request,
        "firebase_enabled": firebase_service.initialized
    })


@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserRegister,
    request: Request,
    db: Session = Depends(get_db)
):
    """Регистрация нового пользователя"""
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует"
        )

    if user_data.username:
        existing_username = db.query(User).filter(User.username == user_data.username).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Это имя пользователя уже занято"
            )

    if not validate_password(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пароль должен содержать минимум 8 символов"
        )

    new_user = User(
        email=user_data.email,
        username=user_data.username,
        display_name=user_data.display_name or user_data.email.split('@')[0],
        hashed_password=get_password_hash(user_data.password),
        is_verified=False
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(days=1)
    ev = EmailVerification(user_id=new_user.id, token=token, expires_at=expires)
    db.add(ev)
    db.commit()

    verification_link = f"{request.url.scheme}://{request.url.hostname}:{request.url.port}/auth/verify-email?token={token}"
    try:
        send_verification_email(new_user.email, verification_link)
    except Exception as ex:
        print(f'⚠️ Не удалось отправить письмо подтверждения: {ex}')

    access_token = create_access_token(data={"sub": str(new_user.id), "email": new_user.email})
    refresh_token = create_refresh_token(data={"sub": str(new_user.id)})

    refresh_token_obj = RefreshToken(
        user_id=new_user.id,
        token=refresh_token,
        expires_at=datetime.utcnow()
    )
    db.add(refresh_token_obj)
    db.commit()

    request.session["user_id"] = new_user.id

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(new_user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """Вход пользователя"""

    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )

    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )

    user.last_login = datetime.utcnow()
    db.commit()

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Установка сессии
    request.session["user_id"] = user.id

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user)
    )


@router.post("/google")
async def google_auth(
    auth_request: GoogleAuthRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Аутентификация через Google"""

    try:
        decoded_token = firebase_service.verify_id_token(auth_request.id_token)
        email = decoded_token.get("email")
        google_id = decoded_token.get("uid")
        display_name = decoded_token.get("name", "")
        avatar_url = decoded_token.get("picture", "")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email не найден в Google токене"
            )

        user = db.query(User).filter(User.email == email).first()

        if not user:
            user = User(
                email=email,
                google_id=google_id,
                firebase_uid=google_id,
                display_name=display_name,
                avatar_url=avatar_url,
                is_verified=True,
                hashed_password=None
            )
            db.add(user)
        else:
            user.google_id = google_id
            user.firebase_uid = google_id
            user.is_verified = True
            user.last_login = datetime.utcnow()

            if not user.avatar_url:
                user.avatar_url = avatar_url

        db.commit()
        db.refresh(user)

        access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        request.session["user_id"] = user.id

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Ошибка Google аутентификации: {str(e)}"
        )


@router.post("/logout")
async def logout(request: Request):
    """Выход пользователя"""
    request.session.clear()
    return {"message": "Успешный выход"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(require_user)):
    """Получить информацию о текущем пользователе"""
    return UserResponse.model_validate(current_user)


@router.get('/verify-email', response_class=HTMLResponse)
async def verify_email(token: str, db: Session = Depends(get_db)):
    ev = db.query(EmailVerification).filter(EmailVerification.token == token).first()
    if not ev or ev.expires_at < datetime.utcnow():
        return templates.TemplateResponse('auth/verify_failed.html', {'request': None, 'message': 'Токен недействителен или просрочен'})

    user = db.query(User).filter(User.id == ev.user_id).first()
    if not user:
        return templates.TemplateResponse('auth/verify_failed.html', {'request': None, 'message': 'Пользователь не найден'})

    user.is_verified = True
    db.delete(ev)
    db.commit()

    return templates.TemplateResponse('auth/verify_success.html', {'request': None, 'message': 'Email успешно подтверждён. Можете войти.'})

@router.get('/firebase-action', response_class=HTMLResponse)
async def firebase_action(request: Request):
    return templates.TemplateResponse('firebase_action.html', {'request': request})
