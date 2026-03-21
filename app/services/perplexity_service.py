from __future__ import annotations

import logging
from typing import Any, Optional
import requests
from datetime import datetime, timedelta, timezone
from app.core.config import get_settings
from app.services.model_rankings import get_models_for, update_rankings, load_rankings

logger = logging.getLogger(__name__)

class PerplexityService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.perplexity_api_key
        ranked = get_models_for('perplexity') or []
        self.model = 'sonar'
        self.base_url = 'https://api.perplexity.ai/v1'

        # health and backoff
        self.healthy: bool = True
        self.failure_count: int = 0
        self.last_failure: Optional[datetime] = None
        self.base_cooldown_seconds: int = 60  # base cooldown on transient errors
        self.auth_cooldown_seconds: int = 3600  # cooldown on auth failures (401)

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
            # cooldown passed — allow retry
            self.healthy = True
            return True
        return True

    def _mark_failure(self, status_code: Optional[int] = None):
        self.failure_count += 1
        self.last_failure = datetime.now(timezone.utc)
        # if auth problem, mark unhealthy longer
        # Only mark unhealthy after repeated failures to avoid blocking providers on single transient error
        if status_code == 401:
            if self.failure_count >= 2:
                self.healthy = False
                logger.warning("Perplexity marked unhealthy due to repeated 401 (auth). Cooldown %s seconds", self.auth_cooldown_seconds)
            else:
                logger.warning("Perplexity received 401 (auth) — will mark unhealthy after repeated failures")
        elif status_code == 429:
            if self.failure_count >= 2:
                self.healthy = False
                logger.warning("Perplexity marked transiently unhealthy due to repeated 429 (rate limit). Failure count %s", self.failure_count)
            else:
                logger.warning("Perplexity rate limited (429) — will mark unhealthy after repeated failures")
        else:
            if self.failure_count >= 2:
                self.healthy = False
                logger.warning("Perplexity marked transiently unhealthy due to repeated errors. Failure count %s", self.failure_count)
            else:
                logger.warning("Perplexity transient error — will mark unhealthy after repeated failures. Failure count %s", self.failure_count)

    def generate_content(self, messages: list[dict[str, str]], model: Optional[str] = None) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("PERPLEXITY_API_KEY не настроен")
        if not self.can_call():
            raise RuntimeError("Perplexity temporarily unavailable (cooldown)")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": 0.2
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            # On success reset failure counters
            self.failure_count = 0
            self.healthy = True
            data = response.json()
            return data
        except requests.HTTPError as ex:
            status = getattr(ex.response, 'status_code', None)
            logger.error("Perplexity request failed: %s", ex)
            self._mark_failure(status_code=status)
            # If auth error, surface clear message
            if status == 401:
                raise RuntimeError("Perplexity API unauthorized (401). Check PERPLEXITY_API_KEY")
            if status == 429:
                raise RuntimeError("Perplexity rate limited (429). Try later")
            raise
        except Exception as ex:
            logger.error("Perplexity request error: %s", ex)
            self._mark_failure()
            raise

    def extract_text(self, response: dict[str, Any]) -> str:
        # Support multiple response shapes
        if not isinstance(response, dict):
            return ""
        # Common OpenAI-style
        choices = response.get("choices") or []
        if choices and isinstance(choices, list):
            first = choices[0]
            if isinstance(first, dict):
                # try 'message' then 'text'
                return first.get("message", {}).get("content", "") or first.get("text", "") or ""
        # fallback to top-level text
        return (response.get("text") or "").strip()

    def reset_health(self):
        """Сбросить состояние health/failure для dev и восстановления вызовов"""
        self.failure_count = 0
        self.healthy = True
        self.last_failure = None

    def refresh_available_models(self) -> list[str]:
        """Perplexity does not offer a public models list in the same way; keep placeholder"""
        # Placeholder: Perplexity requires specific API access; leave it to future enhancements
        return []
