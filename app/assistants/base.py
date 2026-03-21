from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.models.assistant_models import AssistantRequest, AssistantResponse
from app.services.llm_services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.stt_service import STTService


class BaseAssistant(ABC):
    """Базовый контракт для режимов ассистента."""

    def __init__(
        self,
        llm_service: LLMService,
        memory_service: MemoryService,
        stt_service: Optional[STTService] = None,
    ) -> None:
        self.llm_service = llm_service
        self.memory_service = memory_service
        self.stt_service = stt_service

    @abstractmethod
    async def handle(self, request: AssistantRequest) -> AssistantResponse:
        raise NotImplementedError

