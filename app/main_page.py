from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from app.core.fastapi_config import templates
from app.auth.dependencies import require_user
from app.auth.models import User

router = APIRouter()


@router.get("/main", response_class=HTMLResponse)
async def main_page(request: Request, current_user: User = Depends(require_user)):
    """Главная страница приложения, содержит ссылки на подприложения"""
    return templates.TemplateResponse("main.html", {
        "request": request,
        "current_user": current_user,
        "base_url": "/quest-app"
    })

