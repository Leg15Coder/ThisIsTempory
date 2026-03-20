from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import requests
from app.core.config import get_settings
from app.services.model_rankings import get_models_for, update_rankings

logger = logging.getLogger(__name__)

class GroqService:
    """Wrapper for Groq API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = getattr(self.settings, 'groq_api_key', '')
        ranked = get_models_for('groq') or []
        self.default_model = ranked[0] if ranked else "llama-3.3-70b-versatile"
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.timeout = 30

        # Simple cooldown tracking for error handling
        self.unavailable_until = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def is_available(self) -> bool:
        return self.enabled and time.time() > self.unavailable_until

    def refresh_available_models(self) -> list[str]:
        """Groq provides an API to list models; try to refresh and update rankings file."""
        if not self.enabled:
            return []
        try:
            resp = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            models = []
            if isinstance(data, dict) and 'data' in data:
                for item in data['data']:
                    mid = item.get('id')
                    if mid:
                        models.append(mid)
            if models:
                current = get_models_for('groq') or []
                merged = models + [m for m in current if m not in models]
                update_rankings({**{'groq': merged}})
                self.default_model = merged[0]
                return merged
        except Exception as ex:
            logger.debug("Failed to refresh Groq models: %s", ex)
        return []

    def generate_content(self, messages: list[dict[str, str]], model: Optional[str] = None) -> dict[str, Any]:
        """
        Generate content using Groq API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Optional model override

        Returns:
            Dict containing the response content
        """
        if not self.enabled:
            raise RuntimeError("GROQ_API_KEY not configured")

        if not self.is_available():
            raise RuntimeError("Groq service is temporarily unavailable")

        target_model = model or self.default_model

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            logger.info(f"Calling Groq API with model {target_model}")
            response = requests.post(
                self.base_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return {"content": content, "raw": result}

            elif response.status_code == 429:
                # save body and mark cooldown
                try:
                    body = response.text
                except Exception:
                    body = str(response)
                try:
                    from pathlib import Path
                    logs_dir = Path("logs")
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    fp = logs_dir / f"groq_429_{int(time.time())}.json"
                    with fp.open("w", encoding="utf-8") as f:
                        f.write(body)
                    logger.warning("Groq 429 — body saved to %s", str(fp))
                except Exception as ex:
                    logger.warning("Groq 429 and failed to save body: %s", ex)
                self.unavailable_until = time.time() + 60
                raise RuntimeError("Groq Rate Limit Exceeded")

            else:
                try:
                    body = response.text
                except Exception:
                    body = str(response)
                try:
                    from pathlib import Path
                    logs_dir = Path("logs")
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    fp = logs_dir / f"groq_err_{int(time.time())}.json"
                    with fp.open("w", encoding="utf-8") as f:
                        f.write(body)
                    logger.error("Groq API Error %s — body saved to %s", response.status_code, str(fp))
                except Exception as ex:
                    logger.error("Groq API Error %s and failed to save body: %s", response.status_code, ex)
                raise RuntimeError(f"Groq API Error: {response.status_code}")

        except Exception as e:
            logger.exception("Groq request failed")
            raise RuntimeError(f"Groq request failed: {e}")
