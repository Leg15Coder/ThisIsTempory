from fastapi import FastAPI, Request, Form, status
from fastapi.responses import RedirectResponse
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
import random

from app.utils import rarity_class
from app.database import QuestStatus, QuestRarity, Quest, SessionLocal

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


motivations = [
    "Сегодняшний шаг — завтрашняя победа.",
    "Эпический путь состоит из обычных дел.",
    "Каждое дело — это шаг к легенде.",
    "Ты — герой своей истории.",
]


@app.get("/", response_class=HTMLResponse)
async def read_quests(request: Request):
    with SessionLocal() as db:
        quests = db.query(Quest).filter(Quest.status == QuestStatus.active).order_by(Quest.deadline).all()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "quests": quests,
            "now": datetime.now,
            "rarity_class": rarity_class
        })


@app.get("/create", response_class=HTMLResponse)
async def create_quest_form(request: Request):
    return templates.TemplateResponse("create.html", {
        "request": request,
        "now": datetime.now
    })


@app.get("/quest/{quest_id}", response_class=HTMLResponse)
async def read_quests(request: Request, quest_id: int):
    with SessionLocal() as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).one()
        return templates.TemplateResponse("quest.html", {
            "request": request,
            "quest": quest,
            "rarity_class": rarity_class
        })


@app.post("/create")
async def create_quest(
    title: str = Form(...),
    author: str = Form("???"),
    description: str = Form(""),
    deadline_date: str = Form(None),
    deadline_time: str = Form(None),
    rarity: QuestRarity = Form(...)
):
    print(1)

    parsed_deadline = None
    deadline = f"{deadline_date}T{deadline_time}"
    if deadline_date or deadline_time:
        parsed_deadline = datetime.strptime(deadline, "%Y-%m-%dT%H:%M")

    with SessionLocal() as db:
        print(description)
        quest = Quest(
            title=title,
            author=author,
            description=description.replace('\n', '<br>'),
            deadline=parsed_deadline,
            rarity=rarity
        )
        db.add(quest)
        db.commit()
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/complete/{quest_id}")
async def mark_complete(quest_id: int):
    with SessionLocal() as db:
        for q in db.query(Quest).all():
            if q.id == quest_id:
                q.status = QuestStatus.finished
                break
    return RedirectResponse("/today", status_code=303)


@app.post("/fail/{quest_id}")
async def mark_fail(quest_id: int):
    with SessionLocal() as db:
        for q in db.query(Quest).all():
            if q.id == quest_id:
                q.status = QuestStatus.failed
                break
    return RedirectResponse("/today", status_code=303)


@app.get("/today", response_class=HTMLResponse)
async def show_today(request: Request):
    now = datetime.now()
    with SessionLocal() as db:
        todays = [
            q for q in db.query(Quest).all()
            if q.status == QuestStatus.active and q.deadline is not None and q.deadline <= now
        ]
    return templates.TemplateResponse("today.html", {"request": request, "quests": todays})


@app.get("/matrix", response_class=HTMLResponse)
async def matrix(request: Request):
    now = datetime.now()

    urgent_important = []
    urgent_not_important = []
    not_urgent_important = []
    not_urgent_not_important = []

    with SessionLocal() as db:
        for q in db.query(Quest).all():
            if q.status != QuestStatus.active:
                continue
            urgent = q.deadline is not None and q.deadline <= now
            important = q.value.lower() in ["эпический", "легендарный"]
            if urgent and important:
                urgent_important.append(q)
            elif urgent and not important:
                urgent_not_important.append(q)
            elif not urgent and important:
                not_urgent_important.append(q)
            else:
                not_urgent_not_important.append(q)

        return templates.TemplateResponse("matrix.html", {
            "request": request,
            "urgent_important": urgent_important,
            "urgent_not_important": urgent_not_important,
            "not_urgent_important": not_urgent_important,
            "not_urgent_not_important": not_urgent_not_important
        })


@app.get("/archive", response_class=HTMLResponse)
async def archive(request: Request):
    with SessionLocal() as db:
        completed = [q for q in db.query(Quest).all() if q.status == QuestStatus.finished]
        failed = [q for q in db.query(Quest).all() if q.status == QuestStatus.failed]
        return templates.TemplateResponse("archive.html", {"request": request, "completed": completed, "failed": failed})


@app.post("/uncomplete/{quest_id}")
@app.post("/unfail/{quest_id}")
async def return_to_active(quest_id: int):
    with SessionLocal() as db:
        for q in db.query(Quest).all():
            if q.id == quest_id:
                q.status = QuestStatus.active
                break
    return RedirectResponse("/archive", status_code=303)


@app.post("/delete/{quest_id}")
async def delete_quest(quest_id: int):
    with SessionLocal() as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        if quest:
            db.delete(quest)
        return RedirectResponse("/archive", status_code=303)
