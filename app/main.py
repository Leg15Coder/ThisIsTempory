from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from app.tasks.main import router
from app.core.fastapi_config import templates, StaticFiles
from app.physics.models.M1 import router as physics_router_M1
from app.physics.models.M3 import router as physics_router_M3
from app.physics.models.M5 import router as physics_router_M5
from app.physics.models.M10 import router as physics_router_M10
from app.physics.main import router as main_physics_router


app = FastAPI()
app.include_router(physics_router_M1)
app.include_router(physics_router_M3)
app.include_router(physics_router_M5)
app.include_router(physics_router_M10)
app.include_router(main_physics_router)
app.include_router(router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def main_landing(request: Request):
    return templates.TemplateResponse("land.html", {"request": request})
