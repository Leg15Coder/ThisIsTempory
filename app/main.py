import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.fastapi_config import templates
from app.core.config import get_settings

from app.tasks.main import router as tasks_router
from app.auth.routes import router as auth_router
from app.auth.profile_routes import router as profile_router
import app.shop.routes as shop_routes

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
            ensure_db_migrations()
            Base.metadata.create_all(bind=engine)
            print('✅ Таблицы БД проверены/созданы (create_all)')
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

static_dir = settings.static_path if hasattr(settings, 'static_path') else settings.static_dir
from pathlib import Path
if not Path(static_dir).exists():
    fallback = str(Path(__file__).resolve().parent / "static")
    print(f"⚠️ Указанная директория static не найдена: {static_dir}. Попытка использовать fallback: {fallback}")
    if Path(fallback).exists():
        static_dir = fallback
    else:
        print(f"❌ Ни основной, ни fallback static путь не найдены. static_dir={static_dir}, fallback={fallback}")

app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(shop_routes.router)
app.include_router(tasks_router)

@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return FileResponse(os.path.join(static_dir, "sw.js"), media_type="application/javascript")

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
        "connect-src 'self' https://www.googleapis.com https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://www.gstatic.com https://fonts.googleapis.com https://firestore.googleapis.com https://firebaseinstallations.googleapis.com https://apis.google.com https://the-perfect-world-eeddf.firebaseapp.com https://the-perfect-world-eeddf.web.app https://www.googletagmanager.com https://www.google-analytics.com; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.gstatic.com https://www.googleapis.com https://apis.google.com https://accounts.google.com https://ssl.gstatic.com https://www.googletagmanager.com https://www.google-analytics.com; "
        "script-src-elem 'self' 'unsafe-inline' https://www.gstatic.com https://www.googleapis.com https://apis.google.com https://accounts.google.com https://ssl.gstatic.com https://www.googletagmanager.com https://www.google-analytics.com; "
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
