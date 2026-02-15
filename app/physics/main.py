from fastapi import APIRouter, Request

from app.core.fastapi_config import templates

router = APIRouter(prefix="/physics")


@router.get("/")
async def render_m1(request: Request):
    return templates.TemplateResponse("physics/base.html", {
        "request": request,
    })
