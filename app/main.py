from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.tasks.main import router
from app.core.fastapi_config import templates
from app.core.middleware import setup_exception_handlers
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)

app.include_router(router)

app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

setup_exception_handlers(app)


@app.get("/", response_class=HTMLResponse)
async def main_landing(request: Request):
    """Главная посадочная страница"""
    return templates.TemplateResponse("land.html", {"request": request})


@app.on_event("startup")
async def startup_event():
    """Действия при запуске приложения"""
    print(f"{settings.app_name} запущен")
    print(f"Database: {settings.database_url}")


@app.on_event("shutdown")
async def shutdown_event():
    """Действия при остановке приложения"""
    print(f"{settings.app_name} остановлен")

