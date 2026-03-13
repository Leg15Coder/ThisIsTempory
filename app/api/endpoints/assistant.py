from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.assistants.fast_assistant import FastAssistant
from app.assistants.intent_router import IntentRouter
from app.assistants.psych_assistant import PsychAssistant
from app.auth.dependencies import require_user
from app.auth.models import User
from app.models.assistant_models import (
    AssistantRequest,
    AssistantResponse,
    AudioToTextRequest,
    AudioToTextResponse,
    PsychAssistantResponse,
    ConfirmQuestRequest,
    ConfirmQuestResponse,
)
from app.services.gemini_service import GeminiService
from app.services.memory_service import MemoryService
from app.services.stt_service import STTService
from app.tasks.database import get_db
from app.tasks.service import QuestService
from app.tasks.rarity_utils import normalize_to_quest_rarity

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

_memory_service = MemoryService()
_gemini_service = GeminiService()
_stt_service = STTService(_gemini_service)
_intent_router = IntentRouter(_gemini_service)
_fast_assistant = FastAssistant(_gemini_service, _memory_service, _stt_service, _intent_router)
_psych_assistant = PsychAssistant(_gemini_service, _memory_service, _stt_service)


def _ensure_user_scope(request: AssistantRequest, current_user: User) -> AssistantRequest:
    if str(request.user_id) != str(current_user.id):
        request.user_id = str(current_user.id)
    return request


@router.post("/quick", response_model=AssistantResponse)
async def quick_assistant(request: AssistantRequest, current_user: User = Depends(require_user)):
    request = _ensure_user_scope(request, current_user)
    try:
        return await _fast_assistant.handle(request)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Ошибка быстрого ассистента: {ex}")


@router.post("/psych", response_model=PsychAssistantResponse)
async def psych_assistant(request: AssistantRequest, current_user: User = Depends(require_user)):
    request = _ensure_user_scope(request, current_user)
    try:
        result = await _psych_assistant.handle(request)
        return PsychAssistantResponse(response_text=result.response_text, tokens_used=result.tokens_used)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Ошибка психологического режима: {ex}")


@router.post("/audio-to-text", response_model=AudioToTextResponse)
async def audio_to_text(request: AudioToTextRequest, current_user: User = Depends(require_user)):
    try:
        text = await _stt_service.audio_to_text(request.audio, mime_type=request.mime_type)
        return AudioToTextResponse(text=text)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Ошибка распознавания аудио: {ex}")


@router.post("/confirm-quest", response_model=ConfirmQuestResponse)
async def confirm_quest_creation(
    request: ConfirmQuestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    if str(request.user_id) != str(current_user.id):
        request.user_id = str(current_user.id)

    pending = _memory_service.get_pending_action(request.confirmation_token, str(current_user.id))
    if not pending:
        raise HTTPException(status_code=404, detail="Черновик квеста не найден или истёк")

    quest_payload = request.quest.model_dump()
    deadline = None
    if quest_payload.get("deadline_date") or quest_payload.get("deadline_time"):
        date_part = quest_payload.get("deadline_date") or datetime.now().date().isoformat()
        time_part = quest_payload.get("deadline_time") or "00:00"
        try:
            deadline = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
        except Exception:
            deadline = None

    service = QuestService(db, user_id=current_user.id)
    created = service.create_quest(
        title=quest_payload.get("title") or "Новый квест",
        author=quest_payload.get("author") or "AI Assistant",
        description=quest_payload.get("description") or "",
        deadline=deadline,
        rarity=normalize_to_quest_rarity(quest_payload.get("rarity")),
        cost=int(quest_payload.get("cost") or 0),
        parent_ids=None,
        subtasks_data=None,
    )
    _memory_service.delete_pending_action(request.confirmation_token)
    return ConfirmQuestResponse(
        created=True,
        quest_id=str(getattr(created, 'id', None)),
        redirect_to=f"/quest-app/quest/{getattr(created, 'id', '')}",
        message="Квест успешно создан",
    )
