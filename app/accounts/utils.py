from app.core.config import config
from app.core.database import get_db
from app.accounts.models import User
from sqlalchemy.orm import Session
import secrets
from datetime import datetime, timedelta
from fastapi import Request
from typing import Optional
from app.accounts.models import User, EmailVerification, AdminApproval
from app.core.security import get_password_hash, get_username_from_cookies
from fastapi import HTTPException, status


def create_user(db: Session, username: str, email: str, password: str, full_name: str = None) -> tuple[User, str]:
    print(get_user_by_login_or_email(username), get_user_by_login_or_email(email))
    if get_user_by_login_or_email(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь под такой почтой уже существует"
        )
    elif get_user_by_login_or_email(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким логином уже существует"
        )

    user = User(
        login=username,
        email=email,
        hashed_password=get_password_hash(password),
        is_verified=False
    )
    db.add(user)
    db.flush()

    verification_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)

    email_verification = EmailVerification(
        user_id=user.id,
        token=verification_token,
        expires_at=expires_at
    )
    db.add(email_verification)

    admin_approval = AdminApproval(user_id=user.id)
    db.add(admin_approval)

    db.commit()
    db.refresh(user)

    return user, verification_token


def verify_email(db: Session, token: str):
    verification = db.query(EmailVerification).filter(
        EmailVerification.token == token,
        EmailVerification.expires_at > datetime.utcnow()
    ).first()

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Токен подтверждения неверный или устаревший"
        )

    user = db.query(User).filter(User.id == verification.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    user.is_verified = True
    db.delete(verification)
    db.commit()

    return user


def approve_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must verify email first"
        )

    approval = db.query(AdminApproval).filter(AdminApproval.user_id == user_id).first()
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found"
        )

    if approval.approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already approved"
        )

    approval.approved = True
    approval.approved_at = datetime.utcnow()

    user.is_active = True

    db.commit()
    return user


def get_pending_approvals(db: Session):
    return db.query(AdminApproval).filter(AdminApproval.approved == False).all()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_login_or_email(login: str) -> User:
    with next(get_db()) as db:
        user = db.query(User).filter(User.login == login).first()
        if not user:
            user = db.query(User).filter(User.email == login).first()
            if not user:
                return None
        return user


async def auth_required(request: Request) -> User:
    username = await get_username_from_cookies(request)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": f"/accounts/login?redirect={str(request.url)}"}
        )

    user = get_user_by_login_or_email(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь {username} не найден"
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт временно недоступен (сначала подтвердите почту)"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт временно недоступен (ожидайте подтверждение администрацией)"
        )

    return user
