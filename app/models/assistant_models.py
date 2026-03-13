from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class AssistantMode(str, Enum):
    QUICK = "quick"
    PSYCH = "psych"


class IntentType(str, Enum):
    CREATE_EVENT = "create_event"
    SET_REMINDER = "set_reminder"
    CREATE_QUEST = "create_quest"
    NAVIGATE = "navigate"
    QUESTION = "question"
    ANSWER_QUESTION = "answer_question"
    CLARIFY = "clarify"
    UNKNOWN = "unknown"


class IntentResult(BaseModel):
    intent: IntentType = IntentType.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    missing_parameters: list[str] = Field(default_factory=list)


class ActionStatus(str, Enum):
    DRAFT = "draft"
    READY_FOR_CONFIRMATION = "ready_for_confirmation"
    EXECUTED = "executed"


class QuestDraft(BaseModel):
    title: str
    author: str = "???"
    description: str = ""
    rarity: str = "common"
    cost: int = 0
    deadline_date: Optional[str] = None
    deadline_time: Optional[str] = None


class Action(BaseModel):
    type: IntentType
    params: dict[str, Any] = Field(default_factory=dict)
    executed: bool = False
    result: dict[str, Any] = Field(default_factory=dict)
    status: ActionStatus = ActionStatus.DRAFT
    confirmation_token: Optional[str] = None


class AssistantRequest(BaseModel):
    text: Optional[str] = None
    audio: Optional[str] = None
    user_id: str
    session_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_text_or_audio(self) -> "AssistantRequest":
        if not (self.text and self.text.strip()) and not self.audio:
            raise ValueError("Нужен text или audio")
        return self


class AudioToTextRequest(BaseModel):
    audio: str = Field(..., min_length=16)
    mime_type: str = Field(default="audio/webm")
    user_id: Optional[str] = None


class AudioToTextResponse(BaseModel):
    text: str


class AssistantResponse(BaseModel):
    response_text: str
    action: Optional[Action] = None
    requires_clarification: bool = False
    clarification_question: Optional[str] = None
    intent: Optional[IntentResult] = None
    tokens_used: int = 0
    cached: bool = False


class PsychAssistantResponse(BaseModel):
    response_text: str
    tokens_used: int = 0


class MemoryMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[str] = None
    mode: AssistantMode = AssistantMode.QUICK


class AssistantSessionSummary(BaseModel):
    session_id: str
    user_id: str
    mode: AssistantMode
    summary: str = ""


class ConfirmQuestRequest(BaseModel):
    confirmation_token: str
    user_id: str
    session_id: Optional[str] = None
    quest: QuestDraft


class ConfirmQuestResponse(BaseModel):
    created: bool
    quest_id: Optional[str] = None
    redirect_to: Optional[str] = None
    message: str = ""

