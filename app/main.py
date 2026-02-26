import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.fastapi_config import templates
from app.core.config import get_settings

from app.tasks.main import router as tasks_router
from app.auth.routes import router as auth_router
from app.auth.profile_routes import router as profile_router
import app.shop.routes as shop_routes
from app.tasks.database import SessionLocal
from app.auth.models import User as AuthUser
try:
    from app.auth.firestore_user import get_user_by_id as fs_get_user_by_id
except Exception:
    fs_get_user_by_id = None

SESSION_MAX_AGE_IN_SECONDS = 86400 * 30

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler: выполняется при старте и завершении приложения"""
    print(f"{settings.app_name} запущен")
    print(f"Database: {settings.database_url}")
    static_path = getattr(settings, 'static_path', getattr(settings, 'static_dir', None))
    templates_path = getattr(settings, 'templates_path', getattr(settings, 'templates_dir', None))
    print(f"Static path: {static_path}")
    print(f"Templates path: {templates_path}")
    try:
        try:
            import importlib
            importlib.import_module('app.auth.models')
        except Exception as e:
            print('⚠️ Предупреждение: не удалось импортировать модели аутентификации при старте:', e)

        try:
            from app.tasks.database import Base, engine, ensure_db_migrations
            # Если engine не инициализирован (например, FIRESTORE_ENABLED=True), пропускаем создание таблиц
            if engine is not None:
                ensure_db_migrations()
                Base.metadata.create_all(bind=engine)
                print('✅ Таблицы БД проверены/созданы (create_all)')
            else:
                print('ℹ️ SQL engine не инициализирован (вероятно включён FIRESTORE). Пропускаем создание SQL-таблиц.')
        except Exception as e:
            print('⚠️ Предупреждение: не удалось создать таблицы БД при старте:', e)

        yield
    finally:
        print(f"{settings.app_name} остановлен")

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-in-production"),
    max_age=SESSION_MAX_AGE_IN_SECONDS
)


class CurrentUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.current_user = None
        try:
            user_id = None
            try:
                user_id = request.session.get('user_id')
            except Exception:
                user_id = None

            if user_id:
                if SessionLocal is not None:
                    db = SessionLocal()
                    try:
                        user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
                        request.state.current_user = user
                    finally:
                        db.close()
                else:
                    # Firestore mode — try to fetch user document
                    try:
                        if fs_get_user_by_id is not None:
                            u = fs_get_user_by_id(str(user_id))
                            request.state.current_user = u
                    except Exception:
                        request.state.current_user = None
        except Exception as e:
            print('Ошибка при получении current_user в CurrentUserMiddleware:', e)
        response = await call_next(request)
        return response

app.add_middleware(CurrentUserMiddleware)


project_root = Path(__file__).resolve().parent.parent

candidates = [
    project_root / 'public' / 'static',
    project_root / 'static',
    project_root / 'app' / 'static',
    project_root / 'public',
]

try:
    s_path = settings.static_path if hasattr(settings, 'static_path') else None
    if s_path:
        candidates.append(Path(s_path))
except Exception:
    pass

candidates.append(Path(__file__).resolve().parent / 'static')

static_dir = None
for p in candidates:
    try:
        if p and p.exists():
            static_dir = str(p.resolve())
            print(f"ℹ️ Using static directory: {static_dir}")
            break
    except Exception:
        continue

if static_dir is None:
    import tempfile
    temp_static = Path(tempfile.mkdtemp(prefix='motify-static-'))
    print(f"⚠️ Не найден ни один статический каталог; создан временный пустой каталог: {temp_static}")
    static_dir = str(temp_static)

try:
    app.mount('/static', StaticFiles(directory=static_dir), name='static')
except Exception as e:
    print(f"⚠️ Ошибка при монтировании статических файлов {static_dir}: {e}")
    import tempfile
    fallback_dir = Path(tempfile.mkdtemp(prefix='motify-static-fallback-'))
    print(f"⚠️ Монтируется fallback static: {fallback_dir}")
    app.mount('/static', StaticFiles(directory=str(fallback_dir)), name='static')

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(shop_routes.router)
app.include_router(tasks_router)

@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    sw_path = os.path.join(static_dir, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    from fastapi.responses import Response
    return Response("// no service worker available", media_type="application/javascript", status_code=200)

@app.get("/", response_class=HTMLResponse)
async def main_landing(request: Request):
    """Главная посадочная страница - редирект на quest-app или auth"""
    user_id = request.session.get('user_id')

    if user_id:
        return RedirectResponse(url="/quest-app", status_code=303)
    else:
        return templates.TemplateResponse("land.html", {"request": request})

@app.get("/archive")
async def redirect_archive():
    return RedirectResponse(url=f"{settings.root_path if hasattr(settings,'root_path') else ''}/quest-app/archive", status_code=303)

@app.get("/archive/")
async def redirect_archive_slash():
    return RedirectResponse(url=f"{settings.root_path if hasattr(settings,'root_path') else ''}/quest-app/archive", status_code=303)

@app.get("/quest-app")
async def redirect_quest_app_root():
    return RedirectResponse(url=f"{settings.root_path if hasattr(settings,'root_path') else ''}/quest-app/", status_code=307)

@app.middleware("http")
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    # Разрешаем открытие попапов для OAuth (Google) и предотвращаем блокировку
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    # Опционально: response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    csp = (
        "default-src 'self' 'unsafe-inline' https:; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://www.googleapis.com https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://www.gstatic.com https://fonts.googleapis.com https://firestore.googleapis.com https://firebaseinstallations.googleapis.com https://apis.google.com https://firebase.googleapis.com https://the-perfect-world-eeddf.firebaseapp.com https://the-perfect-world-eeddf.web.app https://www.googletagmanager.com https://www.google-analytics.com https://region1.google-analytics.com https://analytics.google.com https://*.google-analytics.com; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.gstatic.com https://www.googleapis.com https://apis.google.com https://accounts.google.com https://ssl.gstatic.com https://www.googletagmanager.com https://www.google-analytics.com https://region1.google-analytics.com https://firebase.googleapis.com; "
        "script-src-elem 'self' 'unsafe-inline' https://www.gstatic.com https://www.googleapis.com https://apis.google.com https://accounts.google.com https://ssl.gstatic.com https://www.googletagmanager.com https://www.google-analytics.com https://region1.google-analytics.com https://firebase.googleapis.com; "
        "script-src-attr 'unsafe-inline'; "
        "frame-src 'self' https://accounts.google.com https://apis.google.com https://oauth.googleusercontent.com https://the-perfect-world-eeddf.firebaseapp.com https://the-perfect-world-eeddf.web.app; "
        "frame-ancestors 'self'; "
    )
    response.headers["Content-Security-Policy"] = csp
    return response

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    public_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'public', 'favicon.ico')
    public_path = os.path.normpath(public_path)

    if os.path.exists(public_path):
        return FileResponse(public_path, media_type='image/x-icon')

    static_fav = os.path.join(static_dir, 'favicon.ico')
    if os.path.exists(static_fav):
        return FileResponse(static_fav, media_type='image/x-icon')
    return FileResponse(os.path.join(static_dir, 'icons', 'icon-192.png'), media_type='image/png')


@app.get('/_debug/current_user')
async def debug_current_user(request: Request):
    if not settings.debug:
        return RedirectResponse(url='/', status_code=303)

    cu = getattr(request.state, 'current_user', None)
    return {
        'session_user_id': request.session.get('user_id'),
        'has_current_user': cu is not None,
        'user': {
            'id': cu.id,
            'email': cu.email,
            'username': cu.username
        } if cu else None
    }
