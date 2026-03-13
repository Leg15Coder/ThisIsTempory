from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

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


@router.get("/main/assistant/confirm", response_class=HTMLResponse)
async def assistant_confirm_page(request: Request, current_user: User = Depends(require_user)):
    token = request.query_params.get("token", "")
    session_id = request.query_params.get("session_id", "assistant-main")
    draft = {
        "title": request.query_params.get("title", ""),
        "author": request.query_params.get("author", "AI Assistant"),
        "description": request.query_params.get("description", ""),
        "rarity": request.query_params.get("rarity", "common"),
        "cost": request.query_params.get("cost", "100"),
        "deadline_date": request.query_params.get("deadline_date", ""),
        "deadline_time": request.query_params.get("deadline_time", ""),
    }
    if not token:
        return RedirectResponse(url="/main", status_code=303)
    return templates.TemplateResponse("assistant_confirm.html", {
        "request": request,
        "current_user": current_user,
        "base_url": "/quest-app",
        "confirmation_token": token,
        "draft": draft,
        "session_id": session_id,
    })


@router.get("/assistant/ui", response_class=HTMLResponse)
async def assistant_ui(request: Request, current_user: User = Depends(require_user)):
    """Возвращает отдельный HTML экран быстрого ассистента — используется для ленивой загрузки в iframe."""
    session_id = request.query_params.get('session_id', 'assistant-main')
    return templates.TemplateResponse('assistant_ui.html', {
        'request': request,
        'current_user': current_user,
        'session_id': session_id,
        'base_url': '/quest-app'
    })
