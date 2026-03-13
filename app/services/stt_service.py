from __future__ import annotations

from app.services.gemini_service import GeminiService


class STTService:
    """Speech-to-Text через Gemini, чтобы не нагружать клиент."""

    def __init__(self, gemini_service: GeminiService) -> None:
        self.gemini_service = gemini_service

    async def audio_to_text(self, audio_base64: str, mime_type: str = "audio/webm") -> str:
        return await self.gemini_service.transcribe_audio(audio_base64, mime_type=mime_type)

