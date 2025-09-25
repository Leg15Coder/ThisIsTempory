from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from app.tasks.main import router
from app.core.fastapi_config import templates, StaticFiles
from app.physics.models.M1 import router as physics_router_M1
from app.physics.models.M3 import router as physics_router_M3


app = FastAPI()
app.include_router(physics_router_M1)
app.include_router(physics_router_M3)
app.include_router(router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def main_landing(request: Request):
    return templates.TemplateResponse("land.html", {"request": request})
