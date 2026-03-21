from __future__ import annotations

from app.assistants.base import BaseAssistant
from app.models.assistant_models import AssistantMode, AssistantRequest, AssistantResponse
from app.services.llm_services.llm_service import LLMService

class PsychAssistant(BaseAssistant):
    # BaseAssistant init takes llm_service

    async def handle(self, request: AssistantRequest) -> AssistantResponse:
        text = request.text.strip() if request.text else ""
        self.memory_service.add_message(request.user_id, "user", text, AssistantMode.PSYCH, session_id=request.session_id)

        context = self.memory_service.get_context(
            request.user_id,
            limit=8,
            session_id=request.session_id,
            mode=AssistantMode.PSYCH,
        )
        summary = None
        if request.session_id:
            summary = self.memory_service.get_summary(request.user_id, request.session_id, AssistantMode.PSYCH)

        # Check if LLMService has any active provider (simple check)
        # Or just try to call generate_text and catch exception
        try:
            result = await self.llm_service.generate_text(
                system_prompt=self.llm_service.get_system_prompt(AssistantMode.PSYCH),
                context_messages=context,
                summary=summary,
                prompt=f"Сообщение пользователя: {text}\nОтветь с эмпатией и поддержкой.",
            )
            response_text = result.get("text") or "Я рядом. Расскажи чуть подробнее, что сейчас ощущается самым тяжёлым."
            tokens_used = result.get("tokens_used", 0)
        except Exception:
            response_text = (
                "Я рядом и готов поддержать. Похоже, тебе сейчас непросто. "
                "Хочешь, помогу аккуратно разобрать ситуацию по шагам и понять, что ты чувствуешь?"
            )
            tokens_used = 0

        self.memory_service.add_message(request.user_id, "assistant", response_text, AssistantMode.PSYCH, session_id=request.session_id)
        return AssistantResponse(response_text=response_text, tokens_used=tokens_used)

