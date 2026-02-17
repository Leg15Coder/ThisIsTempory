from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator

from app.tasks.database import QuestRarity, QuestStatus, SubtaskType


class SubtaskBase(BaseModel):
    """Базовая модель подзадачи"""
    description: str = Field(..., min_length=1, max_length=500)
    weight: int = Field(default=1, ge=1, le=100)
    type: SubtaskType


class CheckboxSubtaskCreate(SubtaskBase):
    """Модель создания чекбокс подзадачи"""
    type: SubtaskType = SubtaskType.checkbox
    completed: bool = False


class NumericSubtaskCreate(SubtaskBase):
    """Модель создания числовой подзадачи"""
    type: SubtaskType = SubtaskType.numeric
    target: float = Field(..., gt=0)
    current: float = Field(default=0, ge=0)


class SubtaskUpdate(BaseModel):
    """Модель обновления подзадачи"""
    completed: Optional[bool] = None
    current: Optional[float] = None


class QuestBase(BaseModel):
    """Базовая модель квеста"""
    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(default="???", max_length=100)
    description: str = Field(default="", max_length=2000)
    rarity: QuestRarity
    cost: int = Field(..., ge=0)


class QuestCreate(QuestBase):
    """Модель создания квеста"""
    deadline: Optional[datetime] = None
    parent_ids: Optional[List[int]] = None
    subtasks: Optional[List[SubtaskBase]] = None

    @validator('parent_ids')
    def validate_parent_ids(cls, v):
        """Валидация списка родительских квестов"""
        if v is not None and len(v) > 10:
            raise ValueError('Максимум 10 родительских квестов')
        return v

    @validator('subtasks')
    def validate_subtasks(cls, v):
        """Валидация списка подзадач"""
        if v is not None and len(v) > 50:
            raise ValueError('Максимум 50 подзадач')
        return v


class QuestUpdate(BaseModel):
    """Модель обновления квеста"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    author: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    deadline: Optional[datetime] = None
    rarity: Optional[QuestRarity] = None
    cost: Optional[int] = Field(None, ge=0)
    status: Optional[QuestStatus] = None
    scope: Optional[str] = None


class QuestResponse(QuestBase):
    """Модель ответа с данными квеста"""
    id: int
    created: datetime
    deadline: Optional[datetime]
    status: QuestStatus
    scope: Optional[str]
    is_new: bool
    progress: int

    class Config:
        from_attributes = True


class QuestProgressResponse(BaseModel):
    """Модель ответа с прогрессом квеста"""
    progress: int = Field(..., ge=0, le=100)
    total: int = Field(..., ge=0)
    completed: float = Field(..., ge=0)


class QuestFilter(BaseModel):
    """Модель фильтрации квестов"""
    search: Optional[str] = Field(None, max_length=100)
    sort_by: Optional[str] = Field(None, regex='^(created|deadline|title|cost|rarity)$')
    sort_order: str = Field(default='asc', regex='^(asc|desc)$')
    status: Optional[QuestStatus] = None
    rarity: Optional[QuestRarity] = None
