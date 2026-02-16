from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.tasks.database import get_db
from app.auth.models import User
from app.auth.security import decode_token
from urllib.parse import quote_plus

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if credentials and credentials.credentials:
        token = credentials.credentials
        try:
            payload = decode_token(token)
            user_id = payload.get('sub')
            if user_id is None:
                return None
            try:
                user = db.query(User).filter(User.id == int(user_id)).first()
            except Exception as e:
                try:
                    from app.tasks.database import ensure_db_migrations
                    ensure_db_migrations()
                    user = db.query(User).filter(User.id == int(user_id)).first()
                except Exception:
                    user = None
            return user
        except Exception:
            return None

    user_id = request.session.get('user_id')
    if user_id:
        try:
            user = db.query(User).filter(User.id == user_id).first()
        except Exception as e:
            try:
                from app.tasks.database import ensure_db_migrations
                ensure_db_migrations()
                user = db.query(User).filter(User.id == user_id).first()
            except Exception:
                user = None
        return user

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
