from fastapi import FastAPI, Request, Form, status
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta as td
import random
from sqlalchemy import or_, case

from app.utils import rarity_class
from app.database import QuestStatus, QuestRarity, Quest, SessionLocal

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def read_quests(request: Request):
    with SessionLocal() as db:
        quests = db.query(Quest).filter(Quest.status == QuestStatus.active).all()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "quests": quests,
            "post_url": "/filter-quests",
            "get_class": rarity_class,
            "main_text": "Активные квесты"
        })


async def flex_quest_filter(quests, sort_type: str, find: str):
    if find is not None:
        search = f"%{find}%"
        quests = quests.filter(
            or_(
                Quest.title.ilike(search),
                Quest.author.ilike(search),
                Quest.description.ilike(search),
                Quest.rarity.ilike(search),
                Quest.status.ilike(search),
            )
        )

        try:
            date_search = datetime.strptime(find, "%Y-%m-%d").date()
            quests = quests.filter(
                or_(
                    Quest.deadline == date_search,
                    Quest.created == date_search,
                )
            )
        except ValueError:
            pass

    if sort_type is not None:
        sort_atr, sort_order = sort_type.split('-')
        is_asc = sort_order != 'desc'
        if sort_atr in ('created', 'deadline', 'title'):
            exec(f'quests = quests.order_by(Quest.{sort_atr}.asc() if is_asc else Quest.{sort_atr}.desc())')
        elif sort_atr == 'rarity':
            order_expr = case(
                {
                    QuestRarity.common: 1,
                    QuestRarity.uncommon: 2,
                    QuestRarity.rare: 3,
                    QuestRarity.epic: 4,
                    QuestRarity.legendary: 5,
                },
                value=Quest.rarity
            )
            quests = quests.order_by(order_expr.asc() if is_asc else order_expr.desc())
    return quests.all()


@app.post("/filter-quests")
async def sort_quests(
    request: Request,
    sort_type: str = Form(None),
    find: str = Form(None),
):
    with SessionLocal() as db:
        quests = db.query(Quest).filter(Quest.status == QuestStatus.active)
        quests = await flex_quest_filter(quests, sort_type, find)

        # Рендерим только блок с карточками
        cards_html = templates.get_template("_quest_cards.html").render(
            request=request,
            quests=quests,
            get_class=rarity_class
        )

        return JSONResponse({"cards_html": cards_html})


@app.post("/archive/filter-quests")
async def sort_archive_quests(
    request: Request,
    sort_type: str = Form(None),
    find: str = Form(None),
):
    with SessionLocal() as db:
        quests = db.query(Quest).filter(Quest.status != QuestStatus.active)
        quests = await flex_quest_filter(quests, sort_type, find)

        # Рендерим только блок с карточками
        cards_html = templates.get_template("_quest_cards.html").render(
            request=request,
            quests=quests,
            get_class=rarity_class
        )

        return JSONResponse({"cards_html": cards_html})


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

    parsed_deadline = None
    if deadline_date or deadline_time:
        if not deadline_time:
            deadline_time = "00:00"
        if not deadline_date:
            deadline_date = datetime.now().date() + td(days=1)

        deadline = f"{deadline_date}T{deadline_time}"
        parsed_deadline = datetime.strptime(deadline, "%Y-%m-%dT%H:%M")

    with SessionLocal() as db:
        quest = Quest(
            title=title,
            author=author,
            description=description,
            deadline=parsed_deadline,
            created=datetime.now(),
            rarity=rarity
        )
        db.add(quest)
        db.commit()
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/complete/{quest_id}")
async def mark_complete(quest_id: int):
    with SessionLocal() as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        quest.status = QuestStatus.finished
        db.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/fail/{quest_id}")
async def mark_fail(quest_id: int):
    with SessionLocal() as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        quest.status = QuestStatus.failed
        db.commit()
    return RedirectResponse("/", status_code=303)


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
        quests = db.query(Quest).filter(Quest.status != QuestStatus.active).all()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "quests": quests,
            "get_class": rarity_class,
            "post_url": "/archive/filter-quests",
            "main_text": "Завершённые квесты"
        })


@app.post("/uncomplete/{quest_id}")
async def return_to_active(quest_id: int):
    with SessionLocal() as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        quest.status = QuestStatus.active
        db.commit()
    return RedirectResponse("/archive", status_code=303)


@app.post("/delete/{quest_id}")
async def delete_quest(quest_id: int):
    with SessionLocal() as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        db.delete(quest)
        db.commit()
        return RedirectResponse("/", status_code=303)
