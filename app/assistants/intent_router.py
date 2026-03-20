from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.models.assistant_models import IntentResult, IntentType
from app.services.llm_service import LLMService

INTENT_PROMPT = """Ты определяешь намерение пользователя в приложении-помощнике.
Доступные действия:
- create_event: создать событие в календаре (нужны: title, date, time, description)
- set_reminder: установить напоминание (нужны: text, time)
- create_quest: создать задачу/квест в приложении (нужны: title, deadline)
- navigate: перейти на другой экран (нужна: page)
- question: просто вопрос, не требующий действия
- clarify: пользователь уточняет свой предыдущий запрос

Сообщение: "{text}"

Ответ ТОЛЬКО в JSON:
{"intent": "name", "confidence": 0.0, "parameters": {}, "missing_parameters": []}
"""


class IntentRouter:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    def _fallback_intent(self, text: str) -> IntentResult:
        """Simple heuristic fallback when LLM is unavailable or returns invalid JSON."""
        lower = (text or "").lower()
        # reminders
        if any(word in lower for word in ["напом", "будиль", "напомни"]):
            return IntentResult(intent=IntentType.SET_REMINDER, confidence=0.55, parameters={}, missing_parameters=["time", "text"])
        # quests/tasks
        if any(word in lower for word in ["квест", "задач", "задач" ]):
            missing = [] if any(char.isdigit() for char in lower) else ["deadline"]
            return IntentResult(intent=IntentType.CREATE_QUEST, confidence=0.6, parameters={"title": text}, missing_parameters=missing)
        # calendar / events
        if any(word in lower for word in ["календар", "событи", "событ", "встреч"]):
            return IntentResult(intent=IntentType.CREATE_EVENT, confidence=0.58, parameters={}, missing_parameters=["title", "date", "time"])
        # navigate
        if any(word in lower for word in ["открой", "перейди", "navigate", "страниц", "главн"]):
            page = "/main" if "main" in lower or "глав" in lower else None
            return IntentResult(intent=IntentType.NAVIGATE, confidence=0.7, parameters={"page": page} if page else {}, missing_parameters=[] if page else ["page"])
        # question heuristic
        if re.search(r"\?|как\s|что\s|почему\s|зачем\s", lower):
            return IntentResult(intent=IntentType.QUESTION, confidence=0.65, parameters={}, missing_parameters=[])
        return IntentResult(intent=IntentType.UNKNOWN, confidence=0.2, parameters={}, missing_parameters=[])

    async def detect_intent(self, text: str) -> IntentResult:
        text = (text or "").strip()
        if not text:
            return IntentResult(intent=IntentType.UNKNOWN, confidence=0.0, missing_parameters=["text"], parameters={})

        # First try fast heuristic
        heuristic = self._fallback_intent(text)
        # If heuristic is confident enough, return it immediately (avoid LLM call)
        if heuristic.confidence and heuristic.confidence >= 0.6 and heuristic.intent != IntentType.UNKNOWN:
            return heuristic

        # Otherwise attempt LLM-based detection (last resort). If it fails, fall back to heuristic.
        try:
            result = await self.llm_service.generate_text(
                prompt=INTENT_PROMPT.format(text=text),
                response_mime_type="application/json",
            )
        except Exception:
            return heuristic

        payload: dict[str, Any] | None = result.get("json")
        if payload is None:
            # try parsing free text as JSON
            try:
                payload = json.loads(result.get("text") or "{}")
            except Exception:
                return heuristic

        if not isinstance(payload, dict):
            return heuristic

        try:
            intent_value = payload.get("intent", IntentType.UNKNOWN.value)
            # compatibility: some prompts may return 'answer_question'
            if intent_value == "answer_question":
                intent_value = IntentType.QUESTION.value

            intent_enum = IntentType(intent_value) if intent_value in IntentType._value2member_map_ else IntentType.UNKNOWN
            confidence = float(payload.get("confidence", 0.0) or 0.0)
            parameters = payload.get("parameters") or {}
            missing = payload.get("missing_parameters") or []

            return IntentResult(intent=intent_enum, confidence=confidence, parameters=parameters, missing_parameters=missing)
        except Exception as ex:
            logging.log(logging.ERROR, ex)
            return heuristic
