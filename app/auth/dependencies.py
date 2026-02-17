from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.tasks.database import get_db
from app.auth.models import User
from app.auth.security import decode_token
from urllib.parse import quote_plus

from types import SimpleNamespace
try:
    from app.auth.firebase_admin import get_firestore_client
except Exception:
    get_firestore_client = None

security = HTTPBearer(auto_error=False)


async def _find_user_in_firestore(firebase_uid: str = None, email: str = None):
    """Поиск пользователя в Firestore: возвращает SimpleNamespace с атрибутами пользователя или None"""
    if get_firestore_client is None:
        return None
    client = get_firestore_client()
    if not client:
        return None

    users_col = client.collection('users')
    try:
        if firebase_uid:
            q = users_col.where('firebase_uid', '==', firebase_uid).limit(1).stream()
            docs = list(q)
            if docs:
                doc = docs[0]
                data = doc.to_dict()
                data['id'] = doc.id
                return SimpleNamespace(**data)
        if email:
            q = users_col.where('email', '==', email).limit(1).stream()
            docs = list(q)
            if docs:
                doc = docs[0]
                data = doc.to_dict()
                data['id'] = doc.id
                return SimpleNamespace(**data)
    except Exception:
        return None
    return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    # Если у нас есть токен (Bearer), сначала попробуем использовать его
    if credentials and credentials.credentials:
        token = credentials.credentials
        try:
            payload = decode_token(token)
            user_id = payload.get('sub')
            if user_id is None:
                return None

            if db is not None:
                try:
                    user = db.query(User).filter(User.id == int(user_id)).first()
                except Exception:
                    user = None
                return user

            # Иначе попробуем Firestore
            try:
                u = await _find_user_in_firestore(firebase_uid=str(user_id))
                if u:
                    return u
            except Exception:
                pass

            return None
        except Exception:
            return None

    user_id = request.session.get('user_id')
    if user_id:
        if db is not None:
            try:
                user = db.query(User).filter(User.id == user_id).first()
            except Exception:
                try:
                    from app.tasks.database import ensure_db_migrations
                    ensure_db_migrations()
                    user = db.query(User).filter(User.id == user_id).first()
                except Exception:
                    user = None
            return user

        try:
            u = await _find_user_in_firestore(firebase_uid=str(user_id))
            return u
        except Exception:
            return None

    return None


async def require_user(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Требует аутентификации: если запрос браузерный — редирект на страницу логина с параметром next, иначе возвращает 401 JSON."""
    if current_user:
        return current_user

    accept = request.headers.get('accept', '')
    x_requested_with = request.headers.get('x-requested-with', '')

    next_url = request.url.path
    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"
    login_url = f"/auth/login?next={quote_plus(next_url)}"

    is_browser_html = 'text/html' in accept and x_requested_with.lower() != 'xmlhttprequest'

    if is_browser_html:
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": login_url})

    # Для AJAX/API возвращаем 401 с JSON
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Требуется аутентификация')


async def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    try:
        return await get_current_user(request, None, db)
    except Exception as ex:
        print(f'Ошибка при определении пользователя из сессии: {ex}')
        return None
