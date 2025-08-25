from fastapi import Request, Form, status, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta as td
from threading import Thread
import json

from app.main import app, templates

from app.tasks.utils import rarity_class
from app.tasks.controller import flex_quest_filter, choose_todays, update_generators
from app.tasks.database import QuestStatus, QuestRarity, Quest, get_db, CheckboxSubtask, NumericSubtask

generators_thread = Thread(target=update_generators, daemon=True)


@app.get("/quest-app", response_class=HTMLResponse)
async def read_quests(request: Request):
    with Depends(get_db) as db:
        quests = db.query(Quest).filter(Quest.status == QuestStatus.active).all()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "quests": quests,
            "post_url": "/filter-quests",
            "get_class": rarity_class,
            "main_text": "Активные квесты"
        })


@app.get("/quest-app/help", response_class=HTMLResponse)
async def read_quests(request: Request):
    return templates.TemplateResponse("help.html", {
        "request": request,
        "now": datetime.now
    })


@app.get("/quest-app/quest/{quest_id}", response_class=HTMLResponse)
async def read_quests(request: Request, quest_id: int):
    with Depends(get_db) as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).one()
        quest.is_new = False
        db.commit()
        return templates.TemplateResponse("quest.html", {
            "request": request,
            "quest": quest,
            "get_class": rarity_class
        })


@app.get("/quest-app/create", response_class=HTMLResponse)
async def create_quest_form(request: Request):
    with Depends(get_db) as db:
        available_quests = db.query(Quest).all()

        return templates.TemplateResponse("create.html", {
            "request": request,
            "now": datetime.now,
            "available_quests": available_quests
        })


@app.post("/quest-app/create")
async def create_quest(
    request: Request = Request,
    title: str = Form(...),
    author: str = Form("???"),
    description: str = Form(""),
    deadline_date: str = Form(None),
    deadline_time: str = Form(None),
    rarity: QuestRarity = Form(...),
    cost: int = Form(...)
):

    parsed_deadline = None
    if deadline_date or deadline_time:
        if not deadline_time:
            deadline_time = "00:00"
        if not deadline_date:
            deadline_date = datetime.now().date() + td(days=1)

        deadline = f"{deadline_date}T{deadline_time}"
        parsed_deadline = datetime.strptime(deadline, "%Y-%m-%dT%H:%M")

    form_data = await request.form()
    parent_quests_ids = form_data.getlist("parent_quests")
    subtasks_data = form_data.getlist("subtasks")

    with Depends(get_db) as db:
        quest = Quest(
            title=title,
            author=author,
            description=description,
            deadline=parsed_deadline,
            created=datetime.now(),
            rarity=rarity,
            cost=cost
        )
        db.add(quest)
        db.flush()

        if parent_quests_ids:
            parents = db.query(Quest).filter(Quest.id.in_(parent_quests_ids)).all()
            quest.parents.extend(parents)

            # Если все родители завершены - квест активен
            if all(p.status == QuestStatus.finished for p in parents):
                await quest.update_status()
        else:
            quest.status = QuestStatus.active

        if subtasks_data:
            for subtask_str in subtasks_data:
                subtask = json.loads(subtask_str)
                if subtask['type'] == 'checkbox':
                    db_subtask = CheckboxSubtask(
                        description=subtask['description'],
                        weight=subtask['weight'],
                        completed=subtask.get('completed', False),
                        quest_id=quest.id
                    )
                elif subtask['type'] == 'numeric':
                    db_subtask = NumericSubtask(
                        description=subtask['description'],
                        weight=subtask['weight'],
                        target=subtask['target'],
                        current=subtask['current'],
                        quest_id=quest.id
                    )
                db.add(db_subtask)

        db.commit()
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/quest-app/today", response_class=HTMLResponse)
async def show_today(request: Request):
    with Depends(get_db) as db:
        todays = await choose_todays(db)
        quests = (db.query(Quest).filter(Quest.status == QuestStatus.active)
                  .filter(Quest.scope == "today")
                  .order_by(Quest.deadline.asc())).all()
        return templates.TemplateResponse("today.html", {
            "request": request,
            "quests": quests,
            "quests_for_approve": todays,
            "get_class": rarity_class
        })


@app.post("/quest-app/today/quest/{quest_id}")
async def mark_today(request: Request, quest_id: int):
    with Depends(get_db) as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        if (await request.form()).get("_method") == "DELETE":
            quest.scope = f"not_today_{datetime.now().date()}"
        else:
            quest.scope = "today"
        db.commit()
    return RedirectResponse("/today", status_code=303)


@app.get("/quest-app/matrix", response_class=HTMLResponse)
async def matrix(request: Request):
    pass


@app.get("/quest-app/archive", response_class=HTMLResponse)
async def archive(request: Request):
    with Depends(get_db) as db:
        quests = db.query(Quest).filter(Quest.status != QuestStatus.active).all()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "quests": quests,
            "get_class": rarity_class,
            "post_url": "/archive/filter-quests",
            "main_text": "Завершённые квесты"
        })


@app.post("/quest-app/filter-quests")
async def sort_quests(
    request: Request,
    sort_type: str = Form(None),
    find: str = Form(None),
):
    with Depends(get_db) as db:
        quests = db.query(Quest).filter(Quest.status == QuestStatus.active)
        quests = await flex_quest_filter(quests, sort_type, find)

        # Рендерим только блок с карточками
        cards_html = templates.get_template("_quest_cards.html").render(
            request=request,
            quests=quests,
            get_class=rarity_class
        )

        return JSONResponse({"cards_html": cards_html})


@app.post("/quest-app/archive/filter-quests")
async def sort_archive_quests(
    request: Request,
    sort_type: str = Form(None),
    find: str = Form(None),
):
    with Depends(get_db) as db:
        quests = db.query(Quest).filter(Quest.status != QuestStatus.active)
        quests = await flex_quest_filter(quests, sort_type, find)

        # Рендерим только блок с карточками
        cards_html = templates.get_template("_quest_cards.html").render(
            request=request,
            quests=quests,
            get_class=rarity_class
        )

        return JSONResponse({"cards_html": cards_html})


@app.post("/quest-app/complete/{quest_id}")
async def mark_complete(quest_id: int):
    with Depends(get_db) as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        quest.status = QuestStatus.finished
        quest.update_status()
        db.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/quest-app/fail/{quest_id}")
async def mark_fail(quest_id: int):
    with Depends(get_db) as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        quest.status = QuestStatus.failed
        quest.update_status()
        db.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/quest-app/uncomplete/{quest_id}")
async def return_to_active(quest_id: int):
    with Depends(get_db) as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        quest.status = QuestStatus.active
        quest.update_status()
        db.commit()
    return RedirectResponse("/archive", status_code=303)


@app.post("/quest-app/delete/{quest_id}")
async def delete_quest(quest_id: int):
    with Depends(get_db) as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        db.delete(quest)
        db.commit()
        return RedirectResponse("/", status_code=303)


@app.post("/quest-app/subtask/{subtask_id}/checkbox")
async def update_checkbox_subtask(subtask_id: int, data: dict):
    with Depends(get_db) as db:
        subtask = db.query(CheckboxSubtask).filter(CheckboxSubtask.id == subtask_id).one()
        subtask.completed = data.get('completed', False)
        db.commit()
        return {"status": "success"}


@app.post("/quest-app/subtask/{subtask_id}/numeric")
async def update_numeric_subtask(subtask_id: int, data: dict):
    with Depends(get_db) as db:
        subtask = db.query(NumericSubtask).filter(NumericSubtask.id == subtask_id).one()
        subtask.current = data.get('current', 0)
        db.commit()
        return {"status": "success"}


@app.get("/quest-app/quest/{quest_id}/progress")
async def get_quest_progress(quest_id: int):
    with Depends(get_db) as db:
        quest = db.query(Quest).filter(Quest.id == quest_id).one()
        return {
            "progress": quest.progress,
            "total": sum(st.weight for st in quest.subtasks),
            "completed": sum(st.weight for st in quest.subtasks if (
                (st.type == 'checkbox' and st.completed) or
                (st.type == 'numeric' and st.current >= st.target)
            ))
        }
