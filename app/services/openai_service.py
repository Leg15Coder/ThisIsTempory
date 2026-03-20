from __future__ import annotations

import logging
from typing import Any, Optional
import requests
from datetime import datetime, timedelta, timezone
from app.core.config import get_settings
from app.services.model_rankings import get_models_for, update_rankings, load_rankings

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.openai_api_key
        ranked = get_models_for('openai') or []
        self.model = self.settings.openai_model or (ranked[0] if ranked else "gpt-3.5-turbo")
        self.base_url = "https://api.openai.com/v1"

        # health/backoff
        self.healthy: bool = True
        self.failure_count: int = 0
        self.last_failure: Optional[datetime] = None
        self.base_cooldown_seconds: int = 30
        self.auth_cooldown_seconds: int = 3600

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def can_call(self) -> bool:
        if not self.enabled:
            return False
        if not self.healthy and self.last_failure:
            cooldown = self.auth_cooldown_seconds if self.failure_count and self.failure_count >= 3 else max(self.base_cooldown_seconds * (2 ** max(0, self.failure_count - 1)), self.base_cooldown_seconds)
            next_allowed = self.last_failure + timedelta(seconds=cooldown)
            if datetime.now(timezone.utc) < next_allowed:
                return False
            self.healthy = True
            return True
        return True

    def _mark_failure(self, status_code: Optional[int] = None):
        self.failure_count += 1
        self.last_failure = datetime.now(timezone.utc)
        # Only mark unhealthy after repeated failures
        if status_code == 401:
            if self.failure_count >= 2:
                self.healthy = False
                logger.warning("OpenAI marked unhealthy due to repeated 401 (auth). Cooldown %s seconds", self.auth_cooldown_seconds)
            else:
                logger.warning("OpenAI received 401 (auth) — will mark unhealthy after repeated failures")
        elif status_code == 429:
            if self.failure_count >= 2:
                self.healthy = False
                logger.warning("OpenAI marked transiently unhealthy due to repeated 429 (rate limit). Failure count %s", self.failure_count)
            else:
                logger.warning("OpenAI rate limited (429) — will mark unhealthy after repeated failures")
        else:
            if self.failure_count >= 2:
                self.healthy = False
                logger.warning("OpenAI marked transiently unhealthy due to repeated errors. Failure count %s", self.failure_count)
            else:
                logger.warning("OpenAI transient error — will mark unhealthy after repeated failures. Failure count %s", self.failure_count)

    def generate_content(self, messages: list[dict[str, str]], model: Optional[str] = None) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("OPENAI_API_KEY не настроен")
        if not self.can_call():
            raise RuntimeError("OpenAI temporarily unavailable (cooldown)")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": 0.7
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            self.failure_count = 0
            self.healthy = True
            return response.json()
        except requests.HTTPError as ex:
            status = getattr(ex.response, 'status_code', None)
            logger.error("OpenAI request failed: %s", ex)
            self._mark_failure(status_code=status)
            if status == 401:
                raise RuntimeError("OpenAI API unauthorized (401). Check OPENAI_API_KEY")
            if status == 429:
                raise RuntimeError("OpenAI rate limited (429). Try later")
            raise
        except Exception as ex:
            logger.error("OpenAI request error: %s", ex)
            self._mark_failure()
            raise

    def extract_text(self, response: dict[str, Any]) -> str:
        choices = response.get("choices") or []
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "").strip()

    def reset_health(self):
        """Сбросить счётчики ошибок и пометку нерабочего состояния (для dev)."""
        self.failure_count = 0
        self.healthy = True
        self.last_failure = None

    def refresh_available_models(self) -> list[str]:
        """Best-effort: fetch models from OpenAI /v1/models and update rankings file."""
        if not self.enabled:
            return []
        try:
            resp = requests.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            models = []
            if isinstance(data, dict) and 'data' in data:
                for item in data['data']:
                    mid = item.get('id')
                    if mid:
                        models.append(mid)
            if models:
                current = load_rankings() or {}
                current['openai'] = models + [m for m in current.get('openai', []) if m not in models]
                update_rankings(current)
                self.model = current['openai'][0]
                return current['openai']
        except Exception as ex:
            logger.debug("OpenAI refresh failed: %s", ex)
        return []
