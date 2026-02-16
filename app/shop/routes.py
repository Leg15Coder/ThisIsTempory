from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List

from app.tasks.database import get_db
from app.auth.dependencies import require_user
from app.auth.models import User
from app.core.fastapi_config import templates
import app.shop.schemas as schemas
from app.shop.service import ShopService, InventoryService, QuestTemplateService

router = APIRouter(tags=["shop"])


@router.get("/shop", response_class=HTMLResponse)
async def shop_page(request: Request, current_user: User = Depends(require_user)):
    return templates.TemplateResponse("shop/shop.html", {"request": request, "user": current_user})


@router.post("/api/shop/items", response_model=schemas.ShopItemResponse)
async def create_shop_item(item_data: schemas.ShopItemCreate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    return ShopService.create_item(db, current_user.id, item_data)


@router.get("/api/shop/items", response_model=List[schemas.ShopItemResponse])
async def get_shop_items(available_only: bool = True, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    return ShopService.get_items(db, current_user.id, available_only)


@router.get("/api/shop/items/{item_id}", response_model=schemas.ShopItemResponse)
async def get_shop_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    item = ShopService.get_item(db, item_id, current_user.id)
    if not item:
        raise HTTPException(status_code=404, detail="Предмет не найден")
    return item


@router.put("/api/shop/items/{item_id}", response_model=schemas.ShopItemResponse)
async def update_shop_item(item_id: int, update_data: schemas.ShopItemUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    return ShopService.update_item(db, item_id, current_user.id, update_data)


@router.delete("/api/shop/items/{item_id}")
async def delete_shop_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    ShopService.delete_item(db, item_id, current_user.id)
    return {"message": "Предмет удалён"}


@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, current_user: User = Depends(require_user)):
    return templates.TemplateResponse("shop/inventory.html", {"request": request, "user": current_user})


@router.get("/api/inventory", response_model=List[schemas.InventoryItemResponse])
async def get_inventory(db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    return InventoryService.get_inventory(db, current_user.id)


@router.post("/api/inventory/purchase", response_model=schemas.InventoryItemResponse)
async def purchase_item(purchase_data: schemas.PurchaseRequest, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    return InventoryService.purchase_item(db, current_user.id, purchase_data.shop_item_id, purchase_data.quantity)


@router.post("/api/inventory/use", response_model=schemas.InventoryItemResponse)
async def use_item(use_data: schemas.UseItemRequest, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    return InventoryService.use_item(db, current_user.id, use_data.inventory_id, use_data.quantity)


@router.get("/quest-templates", response_class=HTMLResponse)
async def quest_templates_page(request: Request, current_user: User = Depends(require_user)):
    return templates.TemplateResponse("shop/quest_templates.html", {"request": request, "user": current_user})


@router.post("/api/quest-templates", response_model=schemas.QuestTemplateResponse)
async def create_quest_template(template_data: schemas.QuestTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    return QuestTemplateService.create_template(db, current_user.id, template_data)


@router.get("/api/quest-templates", response_model=List[schemas.QuestTemplateResponse])
async def get_quest_templates(active_only: bool = False, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    return QuestTemplateService.get_templates(db, current_user.id, active_only)


@router.get("/api/quest-templates/{template_id}", response_model=schemas.QuestTemplateResponse)
async def get_quest_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    template = QuestTemplateService.get_template(db, template_id, current_user.id)
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return template


@router.put("/api/quest-templates/{template_id}", response_model=schemas.QuestTemplateResponse)
async def update_quest_template(template_id: int, update_data: schemas.QuestTemplateUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    return QuestTemplateService.update_template(db, template_id, current_user.id, update_data)


@router.delete("/api/quest-templates/{template_id}")
async def delete_quest_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    QuestTemplateService.delete_template(db, template_id, current_user.id)
    return {"message": "Шаблон удалён"}


@router.post("/api/quest-templates/{template_id}/generate")
async def trigger_quest_generation(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    quest = QuestTemplateService.trigger_generation(db, template_id, current_user.id)
    return {"message": "Квест создан", "quest_id": quest.id}


@router.post("/api/quest-templates/generate-due")
async def generate_due_quests(db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    quests = QuestTemplateService.generate_due_quests(db, current_user.id)
    return {"message": f"Создано квестов: {len(quests)}", "quest_ids": [q.id for q in quests]}
