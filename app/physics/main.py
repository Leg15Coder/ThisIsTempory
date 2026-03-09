from fastapi import APIRouter, Request

from app.core.fastapi_config import templates
from app.physics.models.M21 import router as m21_router
from app.physics.models.M1 import router as render_m1_router
from app.physics.models.M3 import router as render_m3_router
from app.physics.models.M5 import router as render_m5_router
from app.physics.models.M10 import router as render_m10_router

router = APIRouter(prefix="/physics")

router.include_router(m21_router)
router.include_router(render_m1_router)
router.include_router(render_m3_router)
router.include_router(render_m5_router)
router.include_router(render_m10_router)


@router.get("/")
async def render_m1(request: Request):
    return templates.TemplateResponse("physics/base.html", {
        "request": request,
    })
