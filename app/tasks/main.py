from fastapi import Request, Form, status, Depends, APIRouter
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from datetime import datetime, timedelta
from typing import Optional
import json

from sqlalchemy.orm import Session

from app.core.fastapi_config import templates
from app.tasks.utils import rarity_class
from app.tasks.database import QuestStatus, QuestRarity, Quest, get_db
from app.tasks.service import QuestService, SubtaskService
from app.auth.dependencies import require_user
from app.auth.models import User
from app.shop.service import QuestTemplateService
from app.shop.schemas import QuestTemplateCreate

BASE_URL = '/quest-app'
router = APIRouter(prefix=BASE_URL)


def get_quest_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user)
) -> QuestService:
    """Внедрение зависимости для сервиса квестов с user_id"""
    return QuestService(db, user_id=current_user.id)


def get_subtask_service(db: Session = Depends(get_db)) -> SubtaskService:
    """Внедрение зависимости для сервиса подзадач"""
    return SubtaskService(db)


@router.get("/", response_class=HTMLResponse)
async def read_quests(
    request: Request,
    service: QuestService = Depends(get_quest_service),
    current_user: User = Depends(require_user)
):
    """Главная страница с активными квестами"""
    quests = service.get_active_quests()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "quests": quests,
        "post_url": f"{BASE_URL}/filter-quests",
        "get_class": rarity_class,
        "main_text": "Активные квесты",
        "base_url": BASE_URL,
        "current_user": current_user,
    })


@router.get("/help", response_class=HTMLResponse)
async def show_help(
    request: Request,
    current_user: User = Depends(require_user)
):
    """Страница справки"""
    return templates.TemplateResponse("help.html", {
        "request": request,
        "now": datetime.now,
        "base_url": BASE_URL,
        "current_user": current_user,
    })


@router.get("/quest/{quest_id}", response_class=HTMLResponse)
async def show_quest_detail(
    request: Request,
    quest_id: int,
    service: QuestService = Depends(get_quest_service),
    current_user: User = Depends(require_user)
):
    """Детальная страница квеста"""
    quest = service.mark_quest_read(quest_id)
    if not quest:
        return RedirectResponse(url=BASE_URL, status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse("quest.html", {
        "request": request,
        "quest": quest,
        "base_url": BASE_URL,
        "get_class": rarity_class,
        "current_user": current_user,
    })


@router.get("/create", response_class=HTMLResponse)
async def create_quest_form(
    request: Request,
    service: QuestService = Depends(get_quest_service),
    current_user: User = Depends(require_user)
):
    """Форма создания нового квеста"""
    available_quests = service.get_all_quests()

    return templates.TemplateResponse("create.html", {
        "request": request,
        "now": datetime.now,
        "base_url": BASE_URL,
        "available_quests": available_quests,
        "current_user": current_user,
    })


@router.post("/create")
async def create_quest(
    request: Request,
    service: QuestService = Depends(get_quest_service),
    current_user: User = Depends(require_user),
    title: str = Form(...),
    author: str = Form("???"),
    description: str = Form(""),
    deadline_date: Optional[str] = Form(None),
    deadline_time: Optional[str] = Form(None),
    rarity: QuestRarity = Form(...),
    cost: int = Form(...)
):
    """Создание нового квеста"""

    form_data = await request.form()
    is_recurrence = form_data.get("is_recurrence") == "on"

    if is_recurrence:
        try:
            recurrence_type = form_data.get("recurrence_type")
            duration_hours_str = form_data.get("duration_hours")
            duration_hours = int(duration_hours_str) if duration_hours_str else 24

            interval_hours_str = form_data.get("interval_hours")
            interval_hours = int(interval_hours_str) if interval_hours_str else None

            weekdays_list = form_data.getlist("weekdays")
            weekdays = ",".join(weekdays_list) if weekdays_list else None

            template_data = QuestTemplateCreate(
                title=title,
                author=author,
                description=description,
                cost=cost,
                rarity=rarity.value,
                recurrence_type=recurrence_type,
                duration_hours=duration_hours,
                weekdays=weekdays,
                interval_hours=interval_hours,
                start_date=form_data.get("start_date"),
                start_time=form_data.get("start_time"),
                end_date=form_data.get("end_date"),
                end_time=form_data.get("end_time"),
                is_active=True
            )

            QuestTemplateService.create_template(service.db, current_user.id, template_data)

            return RedirectResponse(url="/quest-templates", status_code=status.HTTP_303_SEE_OTHER)
        except Exception as e:
            print(f"Ошибка создания шаблона: {e}")

    parsed_deadline = None
    if deadline_date or deadline_time:
        if not deadline_time:
            deadline_time = "00:00"
        if not deadline_date:
            deadline_date = str(datetime.now().date())

        deadline_str = f"{deadline_date} {deadline_time}"

        try:
            parsed_deadline = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
        except ValueError:
            pass

    form_data = await request.form()
    parent_quests = form_data.getlist("parent_quests")
    subtasks_json = form_data.get("subtasks")

    subtasks_data = None
    if subtasks_json:
        try:
            subtasks_data = json.loads(subtasks_json)
        except json.JSONDecodeError:
            pass

    service.create_quest(
        title=title,
        author=author,
        description=description,
        deadline=parsed_deadline,
        rarity=rarity,
        cost=cost,
        parent_ids=[int(pid) for pid in parent_quests] if parent_quests else None,
        subtasks_data=subtasks_data
    )

    return RedirectResponse(url=BASE_URL, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/today", response_class=HTMLResponse)
async def show_today(
    request: Request,
    service: QuestService = Depends(get_quest_service),
    current_user: User = Depends(require_user)
):
    """Страница с квестами на сегодня"""
    todays_candidates = service.get_todays_candidates()
    todays_quests = service.get_today_quests()

    return templates.TemplateResponse("today.html", {
        "request": request,
        "quests": todays_quests,
        "quests_for_approve": todays_candidates,
        "base_url": BASE_URL,
        "get_class": rarity_class,
        "current_user": current_user,
    })


@router.post("/today/quest/{quest_id}")
async def mark_today(
    request: Request,
    quest_id: int,
    service: QuestService = Depends(get_quest_service)
):
    """Добавить/удалить квест из сегодняшних"""
    form_data = await request.form()

    if form_data.get("_method") == "DELETE":
        scope = f"not_today_{datetime.now().date()}"
    else:
        scope = "today"

    service.set_quest_scope(quest_id, scope)
    return RedirectResponse(f"{BASE_URL}/today", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/archive", response_class=HTMLResponse)
async def show_archive(
    request: Request,
    service: QuestService = Depends(get_quest_service),
    current_user: User = Depends(require_user)
):
    """Страница с завершенными квестами"""
    quests = service.get_archived_quests()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "quests": quests,
        "get_class": rarity_class,
        "post_url": f"{BASE_URL}/archive/filter-quests",
        "main_text": "Завершённые квесты",
        "base_url": BASE_URL,
        "current_user": current_user,
    })


@router.post("/filter-quests")
async def filter_active_quests(
    request: Request,
    service: QuestService = Depends(get_quest_service),
    sort_type: Optional[str] = Form(None),
    find: Optional[str] = Form(None),
):
    """Фильтрация и сортировка активных квестов"""
    db = next(get_db())
    base_query = db.query(Quest).filter(Quest.status == QuestStatus.active)

    sort_by = None
    sort_order = 'asc'
    if sort_type:
        parts = sort_type.split('-')
        if len(parts) == 2:
            sort_by, sort_order = parts

    quests = service.filter_quests(
        base_query=base_query,
        search=find,
        sort_by=sort_by,
        sort_order=sort_order
    )

    cards_html = templates.get_template("_quest_cards.html").render(
        request=request,
        quests=quests,
        get_class=rarity_class
    )

    return JSONResponse({"cards_html": cards_html})


@router.post("/archive/filter-quests")
async def filter_archive_quests(
    request: Request,
    service: QuestService = Depends(get_quest_service),
    sort_type: Optional[str] = Form(None),
    find: Optional[str] = Form(None),
):
    """Фильтрация и сортировка архивных квестов"""
    db = next(get_db())
    base_query = db.query(Quest).filter(Quest.status != QuestStatus.active)

    sort_by = None
    sort_order = 'asc'
    if sort_type:
        parts = sort_type.split('-')
        if len(parts) == 2:
            sort_by, sort_order = parts

    quests = service.filter_quests(
        base_query=base_query,
        search=find,
        sort_by=sort_by,
        sort_order=sort_order
    )

    cards_html = templates.get_template("_quest_cards.html").render(
        request=request,
        quests=quests,
        get_class=rarity_class
    )

    return JSONResponse({"cards_html": cards_html})


@router.post("/complete/{quest_id}")
async def mark_complete(quest_id: int, service: QuestService = Depends(get_quest_service)):
    """Завершить квест успешно"""
    service.complete_quest(quest_id)
    return RedirectResponse(BASE_URL, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/fail/{quest_id}")
async def mark_fail(quest_id: int, service: QuestService = Depends(get_quest_service)):
    """Провалить квест"""
    service.fail_quest(quest_id)
    return RedirectResponse(BASE_URL, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/uncomplete/{quest_id}")
async def return_to_active(quest_id: int, service: QuestService = Depends(get_quest_service)):
    """Вернуть квест в активное состояние"""
    service.return_to_active(quest_id)
    return RedirectResponse(f"{BASE_URL}/archive", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delete/{quest_id}")
async def delete_quest(quest_id: int, service: QuestService = Depends(get_quest_service)):
    """Удалить квест"""
    service.delete_quest(quest_id)
    return RedirectResponse(BASE_URL, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/subtask/{subtask_id}/checkbox")
async def update_checkbox_subtask(
    subtask_id: int,
    data: dict,
    service: SubtaskService = Depends(get_subtask_service)
):
    """Обновить чекбокс подзадачу"""
    subtask = service.update_checkbox_subtask(subtask_id, data.get('completed', False))
    if subtask:
        return {"status": "success"}
    return {"status": "error", "message": "Subtask not found"}


@router.post("/subtask/{subtask_id}/numeric")
async def update_numeric_subtask(
    subtask_id: int,
    data: dict,
    service: SubtaskService = Depends(get_subtask_service)
):
    """Обновить числовую подзадачу"""
    subtask = service.update_numeric_subtask(subtask_id, data.get('current', 0))
    if subtask:
        return {"status": "success"}
    return {"status": "error", "message": "Subtask not found"}


@router.get("/quest/{quest_id}/progress")
async def get_quest_progress(
    quest_id: int,
    service: SubtaskService = Depends(get_subtask_service)
):
    """Получить прогресс квеста"""
    return service.get_quest_progress(quest_id)
