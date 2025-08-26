from sqlalchemy import Column, String
from app.core.database import Base, get_db
from app.core.fastapi_config import templates
from app.accounts.user import get_user_by_login, User
import jwt
import os
from jwt import PyJWTError as JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta, datetime
from typing import Optional

SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = os.environ.get("HASH_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")
if not ALGORITHM:
    raise ValueError("HASH_ALGORITHM environment variable is not set")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)
router = APIRouter()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        return username
    except JWTError:
        return None


async def auth_required(request: Request):
    user = await get_current_user(request)
    print('AUTH')
    if not user:
        """redirect_url = str(request.url)
        response = RedirectResponse(url=f"/login?redirect={redirect_url}", status_code=status.HTTP_303_SEE_OTHER)
        return response"""
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": f"/login?redirect={str(request.url)}"}
        )

    print(user)
    return user


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, redirect: Optional[str] = None):
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse("accounts/login.html", {
        "request": request,
        "redirect_url": redirect or "/dashboard",
        "error": None
    })


@router.post("/login")
async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        redirect_url: str = Form("/")
):
    user_data = get_user_by_login(username)
    if not user_data:
        return templates.TemplateResponse("accounts/login.html", {
            "request": request,
            "redirect_url": redirect_url,
            "error": f"Пользователь с логином {username} не найден"
        })
    elif not verify_password(password, user_data.password):
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
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token")
    return response
