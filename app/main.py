from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from app.tasks.main import router as quests_router
from app.core.security import router as security_router
from app.core.fastapi_config import templates, StaticFiles
from app.core.database import Base, engine


app = FastAPI()

app.include_router(quests_router)
app.include_router(security_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
async def startapp():
    Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("land.html", {"request": request})
