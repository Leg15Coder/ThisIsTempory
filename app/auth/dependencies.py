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

# NEW: import helper to find by doc id in Firestore
try:
    from app.auth.firestore_user import get_user_by_id as fs_get_user_by_id
except Exception:
    fs_get_user_by_id = None

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

            print(f"[DEBUG] get_current_user: bearer token present, user_id={user_id}, db_present={db is not None}")

            if db is not None:
                try:
                    user = db.query(User).filter(User.id == int(user_id)).first()
                except Exception:
                    user = None
                print(f"[DEBUG] get_current_user: SQL lookup result={bool(user)}")
                return user

            # Иначе попробуем Firestore
            try:
                u = await _find_user_in_firestore(firebase_uid=str(user_id))
                print(f"[DEBUG] get_current_user: firestore lookup by firebase_uid result={bool(u)}")
                if u:
                    return u
            except Exception as ex:
                print(f"[DEBUG] get_current_user: firestore lookup by firebase_uid raised: {ex}")
                pass

            return None
        except Exception as ex:
            print(f"[DEBUG] get_current_user: bearer token decode failed: {ex}")
            return None

    user_id = request.session.get('user_id')
    print(f"[DEBUG] get_current_user: no bearer token, session_user_id={user_id}, db_present={db is not None}")
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
            print(f"[DEBUG] get_current_user: SQL session lookup result={bool(user)}")
            return user

        # Firestore mode: сначала попробуем найти документ по ID (session хранит doc id)
        try:
            if fs_get_user_by_id is not None:
                u = fs_get_user_by_id(str(user_id))
                print(f"[DEBUG] get_current_user: firestore lookup by doc id result={bool(u)}")
                if u:
                    return u
        except Exception as ex:
            print(f"[DEBUG] get_current_user: firestore lookup by doc id raised: {ex}")
            pass

        try:
            # fallback: поиск по firebase_uid (на случай, если в session хранится firebase_uid)
            u = await _find_user_in_firestore(firebase_uid=str(user_id))
            print(f"[DEBUG] get_current_user: firestore lookup by firebase_uid fallback result={bool(u)}")
            return u
        except Exception as ex:
            print(f"[DEBUG] get_current_user: firestore lookup by firebase_uid raised: {ex}")
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
