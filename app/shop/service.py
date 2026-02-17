from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException

from app.tasks.database import ShopItem, Inventory, QuestTemplate, Quest
from app.auth.models import User
from app.shop.schemas import (
    ShopItemCreate, ShopItemUpdate,
    QuestTemplateCreate, QuestTemplateUpdate
)


class ShopService:
    """Сервис для работы с магазином"""

    @staticmethod
    def create_item(db: Session, user_id: int, item_data: ShopItemCreate) -> ShopItem:
        item = ShopItem(
            user_id=user_id,
            name=item_data.name,
            description=item_data.description,
            price=item_data.price,
            rarity=item_data.rarity,
            icon=item_data.icon,
            is_available=item_data.is_available,
            stock=item_data.stock
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def get_items(db: Session, user_id: int, available_only: bool = True) -> List[ShopItem]:
        query = db.query(ShopItem).filter(ShopItem.user_id == user_id)
        if available_only:
            query = query.filter(ShopItem.is_available == True)
        return query.all()

    @staticmethod
    def get_item(db: Session, item_id: int, user_id: int) -> Optional[ShopItem]:
        return db.query(ShopItem).filter(
            and_(ShopItem.id == item_id, ShopItem.user_id == user_id)
        ).first()

    @staticmethod
    def update_item(db: Session, item_id: int, user_id: int, update_data: ShopItemUpdate) -> ShopItem:
        item = ShopService.get_item(db, item_id, user_id)
        if not item:
            raise HTTPException(status_code=404, detail="Предмет не найден")

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(item, key, value)

        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def delete_item(db: Session, item_id: int, user_id: int) -> bool:
        item = ShopService.get_item(db, item_id, user_id)
        if not item:
            raise HTTPException(status_code=404, detail="Предмет не найден")
        db.delete(item)
        db.commit()
        return True


class InventoryService:
    """Сервис для работы с инвентарём"""

    @staticmethod
    def get_inventory(db: Session, user_id: int) -> List[Inventory]:
        return db.query(Inventory).filter(Inventory.user_id == user_id).all()

    @staticmethod
    def purchase_item(db: Session, user_id: int, shop_item_id: int, quantity: int = 1) -> Inventory:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        shop_item = db.query(ShopItem).filter(ShopItem.id == shop_item_id).first()
        if not shop_item:
            raise HTTPException(status_code=404, detail="Предмет не найден")

        if not shop_item.is_available:
            raise HTTPException(status_code=400, detail="Предмет недоступен для покупки")

        if shop_item.stock is not None and shop_item.stock < quantity:
            raise HTTPException(status_code=400, detail="Недостаточно товара на складе")

        total_price = shop_item.price * quantity
        if user.currency < total_price:
            raise HTTPException(status_code=400, detail=f"Недостаточно валюты. Нужно: {total_price}, у вас: {user.currency}")

        user.currency -= total_price
        if shop_item.stock is not None:
            shop_item.stock -= quantity

        inventory_entry = db.query(Inventory).filter(
            and_(Inventory.user_id == user_id, Inventory.shop_item_id == shop_item_id)
        ).first()

        if inventory_entry:
            inventory_entry.quantity += quantity
        else:
            inventory_entry = Inventory(user_id=user_id, shop_item_id=shop_item_id, quantity=quantity, used_quantity=0)
            db.add(inventory_entry)

        db.commit()
        db.refresh(inventory_entry)
        return inventory_entry

    @staticmethod
    def use_item(db: Session, user_id: int, inventory_id: int, quantity: int = 1) -> Inventory:
        inventory_entry = db.query(Inventory).filter(
            and_(Inventory.id == inventory_id, Inventory.user_id == user_id)
        ).first()

        if not inventory_entry:
            raise HTTPException(status_code=404, detail="Предмет не найден в инвентаре")

        available = inventory_entry.quantity - inventory_entry.used_quantity
        if available < quantity:
            raise HTTPException(status_code=400, detail=f"Недостаточно предметов. Доступно: {available}")

        inventory_entry.used_quantity += quantity
        inventory_entry.last_used = datetime.now()

        db.commit()
        db.refresh(inventory_entry)
        return inventory_entry


class QuestTemplateService:
    """Сервис для работы с шаблонами периодических квестов"""

    @staticmethod
    def create_template(db: Session, user_id: int, template_data: QuestTemplateCreate) -> QuestTemplate:
        if template_data.recurrence_type == "weekly" and not template_data.weekdays:
            raise HTTPException(status_code=400, detail="Для weekly типа необходимо указать weekdays")

        if template_data.recurrence_type == "interval" and not template_data.interval_hours:
            raise HTTPException(status_code=400, detail="Для interval типа необходимо указать interval_hours")

        start_at = None
        if template_data.start_date or template_data.start_time:
            try:
                date_part = template_data.start_date or datetime.now().date().isoformat()
                time_part = template_data.start_time or "00:00"
                start_at = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
            except Exception:
                start_at = None

        end_at = None
        if template_data.end_date or template_data.end_time:
            try:
                date_part = template_data.end_date or datetime.now().date().isoformat()
                time_part = template_data.end_time or "23:59"
                end_at = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
            except Exception:
                end_at = None

        template = QuestTemplate(
            user_id=user_id,
            title=template_data.title,
            author=template_data.author,
            description=template_data.description,
            cost=template_data.cost,
            rarity=template_data.rarity,
            scope=template_data.scope,
            recurrence_type=template_data.recurrence_type,
            duration_hours=template_data.duration_hours,
            weekdays=template_data.weekdays,
            interval_hours=template_data.interval_hours,
            is_active=template_data.is_active,
            start_at=start_at,
            end_at=end_at
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        return template

    @staticmethod
    def get_templates(db: Session, user_id: int, active_only: bool = False) -> List[QuestTemplate]:
        query = db.query(QuestTemplate).filter(QuestTemplate.user_id == user_id)
        if active_only:
            query = query.filter(QuestTemplate.is_active == True)
        return query.all()

    @staticmethod
    def get_template(db: Session, template_id: int, user_id: int) -> Optional[QuestTemplate]:
        return db.query(QuestTemplate).filter(and_(QuestTemplate.id == template_id, QuestTemplate.user_id == user_id)).first()

    @staticmethod
    def update_template(db: Session, template_id: int, user_id: int, update_data: QuestTemplateUpdate) -> QuestTemplate:
        template = QuestTemplateService.get_template(db, template_id, user_id)
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(template, key, value)

        db.commit()
        db.refresh(template)
        return template

    @staticmethod
    def delete_template(db: Session, template_id: int, user_id: int) -> bool:
        template = QuestTemplateService.get_template(db, template_id, user_id)
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")
        db.delete(template)
        db.commit()
        return True

    @staticmethod
    def generate_due_quests(db: Session, user_id: int) -> List[Quest]:
        templates = QuestTemplateService.get_templates(db, user_id, active_only=True)
        generated = []
        now = datetime.now()
        for t in templates:
            try:
                if t.should_generate(now):
                    q = t.generate_quest(db)
                    generated.append(q)
            except Exception:
                continue
        return generated

    @staticmethod
    def trigger_generation(db: Session, template_id: int, user_id: int) -> Quest:
        template = QuestTemplateService.get_template(db, template_id, user_id)
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")
        return template.generate_quest(db)
