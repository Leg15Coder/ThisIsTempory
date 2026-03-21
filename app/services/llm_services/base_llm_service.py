from enum import IntEnum, StrEnum
import logging
from typing import Optional, Any

from app.core.config import get_settings
from app.models.assistant_models import MemoryMessage, AssistantMode

logger = logging.getLogger(__name__)


class AnswerSize(IntEnum):
    EXTRA_SHORT = 128
    SHORT = 256
    STANDARD = 512
    NORMAL = 1024
    LARGE = 2048
    EXTRA_LARGE = 8192


class ModelTypes(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    EMBEDDING = "embedding"
    SMALL = "small"
    GEOLOCATION = "geolocation"
    IMAGE = "image"
    OTHER = "other"


class BaseLLMService:
    """Базовый класс для LLM сервисов. Конкретные реализации (Gemini, Perplexity, OpenAI) наследуют его и реализуют методы.
    Это позволяет абстрагировать логику ассистента от конкретных провайдеров и легко добавлять новые.
    """
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    def truncate_messages(self, messages: list[MemoryMessage], limit: Optional[int] = None) -> list[MemoryMessage]:
        hard_limit = limit or getattr(self.settings, "assistant_context_messages", 6)
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

    @staticmethod
    def craft_payload(parts: list[dict[str, Any]], size: AnswerSize = AnswerSize.STANDARD, creativity: float = 0.7) -> dict[str, Any]:
        return {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "maxOutputTokens": size.value,
                "temperature": creativity
            }
        }

    def get_next_model(self, model_type: ModelTypes) -> Optional[str]:
        raise NotImplementedError("get_next_model должен быть реализован в наследниках LLMService")

    def update_model(self, model: str, weight: float) -> None:
        raise NotImplementedError("update_model должен быть реализован в наследниках LLMService")

    def craft_url(self, model: str) -> str:
        raise NotImplementedError("craft_url должен быть реализован в наследниках LLMService")

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            return ""

        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        return "\n".join(text_parts).strip()

    def get_system_prompt(self, mode: AssistantMode) -> str:
        if mode == AssistantMode.PSYCH:
            return self.settings.psych_assistant_system_prompt
        return self.settings.fast_assistant_system_prompt

    async def generate_text(self, *args, **kwargs) -> dict[str, Any]:
        raise NotImplementedError("generate_text должен быть реализован в наследниках LLMService")

    async def transcribe_audio(self, audio_base64: str, mime_type: str = "audio/webm") -> str:
        raise NotImplementedError("transcribe_audio должен быть реализован в наследниках LLMService")

    async def generate_embeddings(self, text: str, model: Optional[str] = None) -> list[float] | None:
        raise NotImplementedError("generate_embeddings должен быть реализован в наследниках LLMService")
