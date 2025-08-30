import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from app.accounts.models import User, EmailVerification, AdminApproval

from app.accounts.utils import get_user_by_login_or_email, auth_required
from app.core.security import get_password_hash, verify_password
from app.core.config import config
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from app.core.database import get_db
from app.accounts.email_router import email_service
from app.core.security import get_username_from_cookies, create_access_token
from app.core.fastapi_config import templates
from app.accounts.utils import create_user, verify_email, get_pending_approvals, approve_user

ADMIN_EMAILS = config.ADMIN_EMAILS
router = APIRouter(prefix='/accounts', tags=["accounts"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, redirect: Optional[str] = None):
    user = await get_username_from_cookies(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse("accounts/login.html", {
        "request": request,
        "redirect_url": redirect or "/",
        "error": None
    })


@router.post("/login")
async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        redirect_url: str = Form("/")
):
    user_data = get_user_by_login_or_email(username)
    if not user_data:
        return templates.TemplateResponse("accounts/login.html", {
            "request": request,
            "redirect_url": redirect_url,
            "error": f"Пользователь с логином {username} не найден"
        })
    elif not verify_password(password, user_data.hashed_password):
        return templates.TemplateResponse("accounts/login.html", {
            "request": request,
            "redirect_url": redirect_url,
            "error": "Неверное имя пользователя или пароль"
        })

    access_token = create_access_token(data={"sub": username})
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response


@router.get("/logout")
async def logout(redirect: Optional[str] = None):
    response = RedirectResponse(url=redirect if redirect else "/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token")
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("accounts/register.html", {
        "request": request,
        "error": None
    })


@router.post("/register")
async def register_user(
        request: Request,
        username: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        password_confirm: str = Form(...),
        full_name: str = Form(None),
        db: Session = Depends(get_db)
):
    if password != password_confirm:
        return templates.TemplateResponse("accounts/register.html", {
            "request": request,
            "error": "Пароли не совпадают"
        })

    try:
        user, verification_token = create_user(db, username, email, password, full_name)
        email_service.send_verification_email(user.email, verification_token, user.login)

        for admin_email in ADMIN_EMAILS:
            email_service.send_admin_approval_notification(admin_email, user.login)

        return templates.TemplateResponse("accounts/register_success.html", {
            "request": request,
            "message": "Регистрация успешна! Проверьте вашу почту для подтверждения email."
        })

    except HTTPException as e:
        return templates.TemplateResponse("accounts/register.html", {
            "request": request,
            "error": e.detail
        })


@router.get("/verify-email/{token}", response_class=HTMLResponse)
async def verify_email_page(
        request: Request,
        token: str,
        db: Session = Depends(get_db)
):
    try:
        user = verify_email(db, token)
        return templates.TemplateResponse("accounts/email_verified.html", {
            "request": request,
            "success": True,
            "message": "Email успешно подтвержден! Ожидайте одобрения администратора."
        })
    except HTTPException as e:
        return templates.TemplateResponse("accounts/email_verified.html", {
            "request": request,
            "success": False,
            "message": e.detail
        })


@router.get("/admin/approvals", response_class=HTMLResponse)
async def admin_approvals_page(
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(auth_required)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    pending_approvals = get_pending_approvals(db)
    return templates.TemplateResponse("accounts/admin_approvals.html", {
        "request": request,
        "approvals": pending_approvals
    })


@router.post("/admin/approve/{user_id}")
async def approve_user_by_admin(
        user_id: int,
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(auth_required)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    try:
        user = approve_user(db, user_id)
        email_service.send_approval_confirmation(user.email, user.login)
        return RedirectResponse(url="/accounts/admin/approvals?success=true", status_code=303)

    except HTTPException as e:
        return templates.TemplateResponse("accounts/admin_approvals.html", {
            "request": request,
            "error": e.detail,
            "approvals": get_pending_approvals(db)
        })
