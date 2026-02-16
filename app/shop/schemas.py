from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ShopItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    price: int = Field(..., ge=0)
    rarity: str = Field(default="Обычный")
    icon: Optional[str] = None
    stock: Optional[int] = Field(default=None, ge=0)


class ShopItemCreate(ShopItemBase):
    is_available: bool = True


class ShopItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[int] = Field(None, ge=0)
    rarity: Optional[str] = None
    icon: Optional[str] = None
    is_available: Optional[bool] = None
    stock: Optional[int] = Field(None, ge=0)


class ShopItemResponse(ShopItemBase):
    id: int
    user_id: int
    is_available: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class InventoryItemResponse(BaseModel):
    id: int
    user_id: int
    shop_item_id: int
    quantity: int
    used_quantity: int
    available_quantity: int
    purchased_at: Optional[datetime]
    last_used: Optional[datetime]
    shop_item: ShopItemResponse

    class Config:
        from_attributes = True


class PurchaseRequest(BaseModel):
    shop_item_id: int
    quantity: int = Field(default=1, ge=1)


class UseItemRequest(BaseModel):
    inventory_id: int
    quantity: int = Field(default=1, ge=1)


class QuestTemplateBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: Optional[str] = Field(default="???")
    description: Optional[str] = None
    cost: int = Field(..., ge=0)
    rarity: Optional[str] = Field(default="Обычный")
    scope: Optional[str] = None

    recurrence_type: str = Field(..., description="daily, weekly, interval")
    duration_hours: int = Field(default=24, ge=1)
    weekdays: Optional[str] = Field(None, description="Дни недели через запятую 0-6 (0=пн)")
    interval_hours: Optional[int] = Field(None, ge=1)
    start_date: Optional[str] = Field(None, description="Дата первого запуска")
    start_time: Optional[str] = Field(None, description="Время первого запуска")
    end_date: Optional[str] = Field(None, description="Дата окончания повторов")
    end_time: Optional[str] = Field(None, description="Время окончания повторов")


class QuestTemplateCreate(QuestTemplateBase):
    is_active: bool = True


class QuestTemplateUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    author: Optional[str] = None
    description: Optional[str] = None
    cost: Optional[int] = Field(None, ge=0)
    rarity: Optional[str] = None
    scope: Optional[str] = None
    recurrence_type: Optional[str] = None
    duration_hours: Optional[int] = Field(None, ge=1)
    weekdays: Optional[str] = None
    interval_hours: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class QuestTemplateResponse(QuestTemplateBase):
    id: int
    user_id: int
    is_active: bool
    last_generated: Optional[datetime]
    created_at: Optional[datetime]
    start_at: Optional[datetime]
    end_at: Optional[datetime]

    class Config:
        from_attributes = True
