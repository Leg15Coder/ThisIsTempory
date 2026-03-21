from __future__ import annotations

import hashlib
import math
import time
from datetime import datetime, timedelta
from typing import Optional

from app.assistants.base import BaseAssistant
from app.assistants.intent_router import IntentRouter
from app.models.assistant_models import Action, ActionStatus, AssistantMode, AssistantRequest, AssistantResponse, IntentType
from app.services.memory_service import MemoryService
from app.tasks.rarity_utils import normalize_to_quest_rarity
from app.services.rate_limiter import get_rate_limiter
from app.services.llm_services.llm_service import LLMService


class FastAssistant(BaseAssistant):
    def __init__(self, llm_service: LLMService, memory_service: MemoryService, stt_service, intent_router: IntentRouter) -> None:
        super().__init__(llm_service, memory_service, stt_service)
        self.intent_router = intent_router
        # rate limiter instance (singleton)
        self.rate_limiter = get_rate_limiter()
        # in-memory embedding cache: { cache_key: { 'emb': list[float], 'payload': dict, 'ts': timestamp } }
        self.embedding_cache: dict[str, dict] = {}
        self.embedding_ttl = 7 * 24 * 3600  # 7 days

    async def _resolve_text(self, request: AssistantRequest) -> str:
        if request.text and request.text.strip():
            return request.text.strip()
        if request.audio and self.stt_service:
            mime_type = (request.metadata or {}).get("mime_type", "audio/webm")
            try:
                # LLMService handles rate limits internally or via services
                return (await self.stt_service.audio_to_text(request.audio, mime_type=mime_type)).strip()
            except Exception:
                return ""
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
            token_source = f"quest-confirm:{user_id}:{session_id or ''}:{draft['title']}"
            confirmation_token = hashlib.sha256(token_source.encode("utf-8")).hexdigest()
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

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def _embedding_cache_lookup(self, emb: list[float]) -> Optional[dict]:
        now_ts = time.time()
        best_k = None
        best_score = 0.0
        # scan cache
        for k, v in self.embedding_cache.items():
            if now_ts - v.get("ts", 0) > self.embedding_ttl:
                del self.embedding_cache[k]
                continue
            score = self._cosine_sim(emb, v.get("emb", []))
            if score > best_score:
                best_score = score
                best_k = k
        if best_score > 0.86 and best_k:
            return self.embedding_cache.get(best_k, {}).get("payload")
        return None

    async def handle(self, request: AssistantRequest) -> AssistantResponse:
        text = await self._resolve_text(request)
        cache_key = self._cache_key(request.user_id, text)
        cached = self.memory_service.get_cached_response(cache_key)
        if cached:
            try:
                # LLMService doesn't expose settings directly in same way, but let's assume standard behavior
                # or just skip the dev stub check if not easily accessible
                local_stub = getattr(self.llm_service.settings, 'assistant_local_llm_response', None)
                force_local = getattr(self.llm_service.settings, 'assistant_force_local_llm', False)
                if local_stub and not force_local and isinstance(cached, dict) and cached.get('response_text') == local_stub:
                    try:
                        self.memory_service.delete_cached_response(cache_key)
                    except Exception:
                        pass
                    cached = None
            except Exception:
                pass

        if cached:
            # Ensure we don't pass 'cached' twice (old payloads may include this key)
            try:
                payload = dict(cached)
                payload.pop('cached', None)
            except Exception:
                payload = cached
            payload['cached'] = True
            return AssistantResponse(**payload)

        # compute embedding and try in-memory embedding cache
        emb = None
        try:
            emb = await self.llm_service.generate_embeddings(text)
        except Exception:
            emb = None
        if emb and isinstance(emb, list):
            found = self._embedding_cache_lookup(emb)
            if found:
                try:
                    payload = dict(found)
                    payload.pop('cached', None)
                except Exception:
                    payload = found
                payload['cached'] = True
                return AssistantResponse(**payload)

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
            # store embedding if present
            if emb:
                self.embedding_cache[cache_key] = {"emb": emb, "payload": response.model_dump(), "ts": time.time()}
            return response

        action = self._execute_action(request.user_id, intent, text, session_id=request.session_id)

        response_text = ""
        tokens_used = 0
        raw_llm = None

        if intent.intent in {IntentType.QUESTION, IntentType.UNKNOWN}:
            summary = self.memory_service.get_summary(request.user_id, request.session_id or "quick-default", AssistantMode.QUICK) if request.session_id else None
            context = self.memory_service.get_context(request.user_id, limit=6, session_id=request.session_id, mode=AssistantMode.QUICK)

            try:
                llm = await self.llm_service.generate_text(
                    system_prompt=self.llm_service.get_system_prompt(AssistantMode.QUICK),
                    context_messages=context,
                    summary=summary,
                    prompt=f"Текущий запрос: {text}\nОтветь кратко и по делу.",
                )
                response_text = llm.get("text") or "Пока не удалось сформировать ответ. Попробуй переформулировать запрос."
                tokens_used = llm.get("tokens_used", 0)
                try:
                    raw_llm = str(llm.get('raw') or llm.get('json') or llm.get('text') or llm.get('raw_text') or '')
                except Exception:
                    raw_llm = None
            except Exception as ex:
                response_text = "Извините, сервис временно недоступен. Попробуйте позже."
                raw_llm = str(ex)
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
            raw_llm_response=raw_llm,
        )
        self.memory_service.add_message(request.user_id, "assistant", response.response_text, AssistantMode.QUICK, session_id=request.session_id)
        self.memory_service.set_cached_response(cache_key, response.model_dump())
        if emb:
            self.embedding_cache[cache_key] = {"emb": emb, "payload": response.model_dump(), "ts": time.time()}
        return response
