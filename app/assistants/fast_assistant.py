from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from app.assistants.base import BaseAssistant
from app.assistants.intent_router import IntentRouter
from app.models.assistant_models import Action, ActionStatus, AssistantMode, AssistantRequest, AssistantResponse, IntentType
from app.services.memory_service import MemoryService
from app.tasks.rarity_utils import normalize_to_quest_rarity


class FastAssistant(BaseAssistant):
    def __init__(self, gemini_service, memory_service: MemoryService, stt_service, intent_router: IntentRouter) -> None:
        super().__init__(gemini_service, memory_service, stt_service)
        self.intent_router = intent_router

    async def _resolve_text(self, request: AssistantRequest) -> str:
        if request.text and request.text.strip():
            return request.text.strip()
        if request.audio and self.stt_service:
            mime_type = (request.metadata or {}).get("mime_type", "audio/webm")
            return (await self.stt_service.audio_to_text(request.audio, mime_type=mime_type)).strip()
        return ""

    def _cache_key(self, user_id: str, text: str) -> str:
        return hashlib.sha256(f"quick:{user_id}:{text.lower().strip()}".encode("utf-8")).hexdigest()

    def _build_quest_draft(self, params: dict, text: str) -> dict:
        title = (params.get("title") or text[:200] or "Новый квест").strip()
        rarity = normalize_to_quest_rarity(params.get("rarity")).name if params.get("rarity") else "common"
        deadline_date = params.get("deadline_date") or params.get("date")
        deadline_time = params.get("deadline_time") or params.get("time") or "18:00"
        if not deadline_date and any(word in text.lower() for word in ["завтра"]):
            deadline_date = (datetime.now() + timedelta(days=1)).date().isoformat()
        return {
            "title": title,
            "author": params.get("author") or "AI Assistant",
            "description": params.get("description") or text,
            "rarity": rarity,
            "cost": int(params.get("cost") or 100),
            "deadline_date": deadline_date,
            "deadline_time": deadline_time,
        }

    def _execute_action(self, user_id: str, intent, text: str, session_id: str | None = None) -> Action | None:
        params = dict(intent.parameters or {})
        if intent.intent == IntentType.NAVIGATE:
            page = params.get("page") or "/main"
            return Action(type=IntentType.NAVIGATE, params={"page": page}, executed=True, status=ActionStatus.EXECUTED, result={"redirect_to": page})
        if intent.intent == IntentType.CREATE_EVENT:
            result = self.memory_service.create_event(user_id, params)
            return Action(type=IntentType.CREATE_EVENT, params=params, executed=bool(result.get("created")), status=ActionStatus.EXECUTED if result.get("created") else ActionStatus.DRAFT, result=result)
        if intent.intent == IntentType.SET_REMINDER:
            result = self.memory_service.set_reminder(user_id, params)
            return Action(type=IntentType.SET_REMINDER, params=params, executed=True, status=ActionStatus.EXECUTED, result=result)
        if intent.intent == IntentType.CREATE_QUEST:
            draft = self._build_quest_draft(params, text)
            confirmation_token = hashlib.sha256(f"quest-confirm:{user_id}:{session_id}:{draft['title']}".encode("utf-8")).hexdigest()
            self.memory_service.save_pending_action(confirmation_token, user_id, {"type": IntentType.CREATE_QUEST.value, "quest": draft}, session_id=session_id)
            return Action(
                type=IntentType.CREATE_QUEST,
                params=draft,
                executed=False,
                status=ActionStatus.READY_FOR_CONFIRMATION,
                confirmation_token=confirmation_token,
                result={
                    "message": "Черновик квеста подготовлен",
                    "quest": draft,
                    "confirm_endpoint": "/api/assistant/confirm-quest",
                },
            )
        return None

    async def handle(self, request: AssistantRequest) -> AssistantResponse:
        text = await self._resolve_text(request)
        cache_key = self._cache_key(request.user_id, text)
        cached = self.memory_service.get_cached_response(cache_key)
        if cached:
            return AssistantResponse(**cached, cached=True)

        intent = await self.intent_router.detect_intent(text)
        self.memory_service.add_message(request.user_id, "user", text, AssistantMode.QUICK, session_id=request.session_id)

        if intent.missing_parameters:
            question = f"Уточни, пожалуйста: {', '.join(intent.missing_parameters)}."
            response = AssistantResponse(
                response_text=question,
                requires_clarification=True,
                clarification_question=question,
                intent=intent,
            )
            self.memory_service.add_message(request.user_id, "assistant", response.response_text, AssistantMode.QUICK, session_id=request.session_id)
            self.memory_service.set_cached_response(cache_key, response.model_dump())
            return response

        action = self._execute_action(request.user_id, intent, text, session_id=request.session_id)

        if intent.intent in {IntentType.QUESTION, IntentType.UNKNOWN}:
            summary = self.memory_service.get_summary(request.user_id, request.session_id or "quick-default", AssistantMode.QUICK) if request.session_id else None
            context = self.memory_service.get_context(request.user_id, limit=6, session_id=request.session_id, mode=AssistantMode.QUICK)
            llm = await self.gemini_service.generate_text(
                system_prompt=self.gemini_service.get_system_prompt(AssistantMode.QUICK),
                context_messages=context,
                summary=summary,
                prompt=f"Текущий запрос: {text}\nОтветь кратко и по делу.",
            )
            response_text = llm.get("text") or "Пока не удалось сформировать ответ. Попробуй переформулировать запрос."
            tokens_used = llm.get("tokens_used", 0)
        else:
            response_text = "Действие подготовлено."
            if action and action.type == IntentType.NAVIGATE:
                response_text = f"Перехожу на страницу {action.result.get('redirect_to')}."
            elif action and action.type == IntentType.CREATE_EVENT:
                response_text = "Событие подготовлено и отправлено в Google Calendar."
            elif action and action.type == IntentType.SET_REMINDER:
                response_text = "Напоминание подготовлено и сохранено в памяти приложения."
            elif action and action.type == IntentType.CREATE_QUEST:
                response_text = "Я подготовил черновик квеста. Проверь детали и подтверди создание на экране подтверждения."
            tokens_used = 0

        response = AssistantResponse(
            response_text=response_text,
            action=action,
            requires_clarification=False,
            clarification_question=None,
            intent=intent,
            tokens_used=tokens_used,
        )
        self.memory_service.add_message(request.user_id, "assistant", response.response_text, AssistantMode.QUICK, session_id=request.session_id)
        self.memory_service.set_cached_response(cache_key, response.model_dump())
        return response

