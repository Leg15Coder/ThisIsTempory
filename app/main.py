import logging

from app.accounts.models import AdminApproval
from app.core.config import config
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from app.tasks.main import router as quests_router
from app.accounts.service import router as accounts_router
from app.core.fastapi_config import templates, StaticFiles
from app.core.database import Base, engine, get_db
from app.accounts.utils import create_user, HTTPException


app = FastAPI()

app.include_router(quests_router)
app.include_router(accounts_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
async def startapp():
    Base.metadata.create_all(bind=engine)
    try:
        with next(get_db()) as db:
            admin, _ = create_user(db, config.ADMIN_NAME, config.ADMIN_EMAIL, config.ADMIN_PASSWORD)

            admin.is_admin = True
            admin.is_verified = True
            admin.is_active = True

            approve = db.quesry(AdminApproval).filter(AdminApproval.user_id == admin.id).first()
            if approve:
                approval.approved = True
                approval.approved_at = datetime.utcnow()

            db.commit()
            db.flush()

        logging.info("Регистрация администратора прошла успешно")
    except HTTPException:
        logging.info("Администратор уже зарегистрирован")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("land.html", {"request": request})
