from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import requests

from app.core.config import get_settings
from app.models.assistant_models import AssistantMode, MemoryMessage

logger = logging.getLogger(__name__)


class GeminiService:
    """Лёгкая обёртка над Gemini API с ретраями, учётом токенов и усечением контекста."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.gemini_api_key
        self.base_url = self.settings.gemini_base_url.rstrip("/")
        self.default_model = self.settings.gemini_model
        self.intent_model = self.settings.gemini_intent_model or self.default_model
        self.audio_model = self.settings.gemini_audio_model or self.default_model
        self.timeout = self.settings.gemini_timeout_seconds
        self.max_retries = self.settings.gemini_max_retries
        self.max_context_messages = self.settings.assistant_context_messages

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    def truncate_messages(self, messages: list[MemoryMessage], limit: Optional[int] = None) -> list[MemoryMessage]:
        hard_limit = limit or self.max_context_messages
        if hard_limit <= 0:
            return []
        return messages[-hard_limit:]

    def build_context_text(self, messages: list[MemoryMessage], summary: Optional[str] = None) -> str:
        chunks: list[str] = []
        if summary:
            chunks.append(f"Краткое резюме прошлой переписки: {summary}")
        for item in self.truncate_messages(messages):
            chunks.append(f"{item.role}: {item.content}")
        return "\n".join(chunks).strip()

    def _post_generate_content(self, model: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("GEMINI_API_KEY не настроен")

        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
        payload = {"contents": [{"parts": parts}]}
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except Exception as ex:
                last_error = ex
                logger.warning("Gemini request failed on attempt %s/%s: %s", attempt, self.max_retries, ex)
                if attempt < self.max_retries:
                    time.sleep(min(2 ** (attempt - 1), 4))

        raise RuntimeError(f"Gemini request failed after retries: {last_error}")

    def _extract_text(self, data: dict[str, Any]) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        return "\n".join(text_parts).strip()

    async def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: Optional[str] = None,
        context_messages: Optional[list[MemoryMessage]] = None,
        summary: Optional[str] = None,
        model: Optional[str] = None,
        response_mime_type: Optional[str] = None,
    ) -> dict[str, Any]:
        all_parts: list[dict[str, Any]] = []
        if system_prompt:
            all_parts.append({"text": f"SYSTEM:\n{system_prompt.strip()}"})
        if context_messages:
            context_text = self.build_context_text(context_messages, summary=summary)
            if context_text:
                all_parts.append({"text": f"CONTEXT:\n{context_text}"})
        all_parts.append({"text": prompt.strip()})

        raw = self._post_generate_content(model or self.default_model, all_parts)
        text = self._extract_text(raw)
        usage_text = "\n".join(part.get("text", "") for part in all_parts)
        result: dict[str, Any] = {
            "text": text,
            "raw": raw,
            "tokens_used": self.estimate_tokens(usage_text) + self.estimate_tokens(text),
        }
        if response_mime_type == "application/json":
            parsed_json: dict[str, Any] | None
            try:
                parsed_json = json.loads(text)
            except Exception:
                parsed_json = None
            result["json"] = parsed_json
        return result

    async def transcribe_audio(self, audio_base64: str, mime_type: str = "audio/webm") -> str:
        prompt = "Преобразуй аудио в точный текст на русском языке. Верни только распознанный текст без комментариев."
        raw = self._post_generate_content(
            self.audio_model,
            [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": audio_base64}},
            ],
        )
        text = self._extract_text(raw)
        return text.strip()

    def get_system_prompt(self, mode: AssistantMode) -> str:
        if mode == AssistantMode.PSYCH:
            return self.settings.psych_assistant_system_prompt
        return self.settings.fast_assistant_system_prompt
