from __future__ import annotations

import json
import re
from typing import Any

from app.models.assistant_models import IntentResult, IntentType
from app.services.gemini_service import GeminiService


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
{{"intent": "name", "confidence": 0.0, "parameters": {{}}, "missing_parameters": []}}
"""


class IntentRouter:
    def __init__(self, gemini_service: GeminiService) -> None:
        self.gemini_service = gemini_service

    def _fallback_intent(self, text: str) -> IntentResult:
        lower = text.lower()
        if any(word in lower for word in ["напом", "будиль", "напомни"]):
            return IntentResult(intent=IntentType.SET_REMINDER, confidence=0.55, parameters={}, missing_parameters=["time", "text"])
        if any(word in lower for word in ["квест", "задач"]):
            missing = [] if any(char.isdigit() for char in lower) else ["deadline"]
            return IntentResult(intent=IntentType.CREATE_QUEST, confidence=0.6, parameters={"title": text}, missing_parameters=missing)
        if any(word in lower for word in ["календар", "событи", "встреч"]):
            return IntentResult(intent=IntentType.CREATE_EVENT, confidence=0.58, parameters={}, missing_parameters=["title", "date", "time"])
        if any(word in lower for word in ["открой", "перейди", "navigate", "страниц"]):
            page = "/main" if "main" in lower or "глав" in lower else None
            return IntentResult(intent=IntentType.NAVIGATE, confidence=0.7, parameters={"page": page} if page else {}, missing_parameters=[] if page else ["page"])
        if re.search(r"\?|как |что |почему |зачем ", lower):
            return IntentResult(intent=IntentType.QUESTION, confidence=0.65)
        return IntentResult(intent=IntentType.UNKNOWN, confidence=0.2)

    async def detect_intent(self, text: str) -> IntentResult:
        text = (text or "").strip()
        if not text:
            return IntentResult(intent=IntentType.UNKNOWN, confidence=0.0, missing_parameters=["text"])

        if not self.gemini_service.enabled:
            return self._fallback_intent(text)

        result = await self.gemini_service.generate_text(
            prompt=INTENT_PROMPT.format(text=text),
            model=self.gemini_service.intent_model,
            response_mime_type="application/json",
        )
        payload: dict[str, Any] | None = result.get("json")
        if payload is None:
            try:
                payload = json.loads(result.get("text") or "{}")
            except Exception:
                return self._fallback_intent(text)

        try:
            intent_value = payload.get("intent", IntentType.UNKNOWN.value)
            if intent_value == "answer_question":
                intent_value = IntentType.QUESTION.value
            return IntentResult(
                intent=IntentType(intent_value),
                confidence=float(payload.get("confidence", 0.0) or 0.0),
                parameters=payload.get("parameters") or {},
                missing_parameters=payload.get("missing_parameters") or [],
            )
        except Exception:
            return self._fallback_intent(text)

