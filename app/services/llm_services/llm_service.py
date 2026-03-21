from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.config import get_settings
from app.models.assistant_models import AssistantMode, MemoryMessage
from app.services.llm_services.gemini_service import GeminiService
from app.services.groq_service import GroqService
from app.services.llm_services.base_llm_service import BaseLLMService
from app.services.mistral_service import MistralService
from app.services.zhipu_service import ZhipuService
from app.services.openrouter_service import OpenRouterService
from app.services.perplexity_service import PerplexityService
from app.services.openai_service import OpenAIService
from app.services.rate_limiter import get_rate_limiter
from app.services import token_utils
import time

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self) -> None:
        self.settings = get_settings()

        self.providers_order: list[tuple[str, BaseLLMService]] = [
            ("gemini", GeminiService()),
            # ("groq", GroqService()),
            # ("mistral", MistralService()),
            # ("zhipu", ZhipuService()),
            # ("openrouter", OpenRouterService()),
            # ("perplexity", PerplexityService()),
            # ("openai", OpenAIService()),
        ]

        self.provider_status: dict[str, dict] = {}
        for name, _ in self.providers_order:
            self.provider_status[name] = {
                'last_success': 0.0,
                'last_failure': 0.0,
                'failure_count': 0,
            }

        redis_url = getattr(self.settings, 'redis_url', None)
        self.rate_limiter = get_rate_limiter(redis_url=redis_url, rpm=getattr(self.settings, 'llm_rpm', 60), rpd=getattr(self.settings, 'llm_rpd', 1000))

    @staticmethod
    def _convert_to_openai_messages(prompt: str, system_prompt: Optional[str], context_messages: Optional[list[MemoryMessage]], summary: Optional[str]) -> list[dict[str, str]]:
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if summary:
            messages.append({"role": "system", "content": f"Summary of previous conversation: {summary}"})

        if context_messages:
            for msg in context_messages:
                role = msg.role if msg.role in ["user", "assistant", "system"] else "user"
                messages.append({"role": role, "content": msg.content})

        messages.append({"role": "user", "content": prompt})
        return messages

    def __sort_key(self, item: tuple[str, object]) -> tuple:
        pname, prov = item
        st = self.provider_status.get(pname, {})
        enabled_score = 0 if getattr(prov, 'enabled', True) else 1
        failures = st.get('failure_count', 0)
        last_success = st.get('last_success', 0.0)
        last_failure = st.get('last_failure', 0.0)
        nowt = time.time()
        recent_failure_penalty = 1 if (nowt - last_failure) < max(30, failures * 10) else 0
        return enabled_score, failures + recent_failure_penalty, -int(last_success)

    async def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: Optional[str] = None,
        context_messages: Optional[list[MemoryMessage]] = None,
        summary: Optional[str] = None,
        response_mime_type: Optional[str] = None,
        max_tokens: int = 1024
    ) -> dict[str, Any]:

        if getattr(self.settings, 'assistant_force_local_llm', False):
            return {
                "text": getattr(self.settings, 'assistant_local_llm_response', "(DEV) Local Response"),
                "raw": {},
                "provider": "local"
            }

        try:
            context_limit = getattr(self.settings, 'assistant_context_token_budget', None) or 800
            context_limit = min(context_limit, int(max_tokens))
            use_summary_threshold = getattr(self.settings, 'assistant_summary_threshold_tokens', 1200)
            if context_messages:
                total_est = sum(token_utils.estimate_tokens(m.content or '') for m in context_messages)
                if total_est > use_summary_threshold:
                    summary = token_utils.summarize_context(context_messages, max_summary_tokens=200)
                    context_messages = token_utils.truncate_messages(context_messages, token_budget=context_limit)
                else:
                    context_messages = token_utils.truncate_messages(context_messages, token_budget=context_limit)
        except Exception as e:
            logger.debug('Context truncation/summarization failed: %s', e)

        # messages = self._convert_to_openai_messages(prompt, system_prompt, context_messages, summary)
        messages = context_messages or []

        last_error = None
        sorted_providers = sorted(self.providers_order, key=lambda p: self.__sort_key(p))

        for provider_name, provider in sorted_providers:
            if not provider.enabled:
                logger.debug("Провайдер %s недоступен, пропускаем его", provider_name)
                continue

            try:
                result = await provider.generate_text(prompt, system_prompt, messages, summary, response_mime_type)
                text_content = result.get("text")
                response_data = result.get("raw", {})

                ps = self.provider_status.get(provider_name)
                if ps is not None:
                    ps['last_success'] = time.time()
                    ps['failure_count'] = 0

                return {"text": text_content, "raw": response_data, "provider": provider_name}

            except Exception as e:
                logger.warning("Провайдер %s недоступен или вернул некорректный контент: %s", provider_name, e)
                last_error = e
                ps = self.provider_status.get(provider_name)
                if ps is not None:
                    ps['failure_count'] = ps.get('failure_count', 0) + 1
                    ps['last_failure'] = time.time()
                continue

        logger.error("Запросы ко всем провайдерам вернули ошибки. Последняя ошибка: %s", last_error)
        return {"text": "Извините, сейчас я не могу ответить. Попробуйте позже.", "raw": {}, "provider": "none", "error": str(last_error)}

    async def generate_embeddings(self, text: str) -> list[float]:
        for provider_name, provider in self.providers_order:
            try:
                return await provider.generate_embeddings(text)
            except Exception as ex:
                logger.error("Ошибка подсчёта эмбендингов у провайдера %s: %s", provider_name, ex)
        return []

    async def transcribe_audio(self, audio_base64: str, mime_type: str = "audio/webm") -> str:
        for provider_name, provider in self.providers_order:
            try:
                return await provider.transcribe_audio(audio_base64, mime_type)
            except Exception as ex:
                logger.error("Ошибка транскрипции аудио у провайдера %s: %s", provider_name, ex)
        return ""

    def get_system_prompt(self, mode: AssistantMode) -> str:
        return self.providers_order[0][1].get_system_prompt(mode)
