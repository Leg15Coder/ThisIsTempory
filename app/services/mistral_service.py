from __future__ import annotations
import json
import logging
import time
from typing import Any, Optional

import requests
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class MistralService:
    """Wrapper for Mistral API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = getattr(self.settings, 'mistral_api_key', '')
        self.default_model = "mistral-small-latest"
        self.base_url = "https://api.mistral.ai/v1/chat/completions"
        self.timeout = 30
        self.unavailable_until = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def is_available(self) -> bool:
        return self.enabled and time.time() > self.unavailable_until

    def generate_content(self, messages: list[dict[str, str]], model: Optional[str] = None) -> dict[str, Any]:
        """
        Generate content using Mistral API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Optional model override

        Returns:
            Dict containing the response content
        """
        if not self.enabled:
            raise RuntimeError("MISTRAL_API_KEY not configured")

        if not self.is_available():
            raise RuntimeError("Mistral service is temporarily unavailable")

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
            logger.info(f"Calling Mistral API with model {target_model}")
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
                try:
                    body = response.text
                except Exception:
                    body = str(response)
                try:
                    from pathlib import Path
                    logs_dir = Path("logs")
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    fp = logs_dir / f"mistral_429_{int(time.time())}.json"
                    with fp.open("w", encoding="utf-8") as f:
                        f.write(body)
                    logger.warning("Mistral 429 — body saved to %s", str(fp))
                except Exception as ex:
                    logger.warning("Mistral 429 and failed to save body: %s", ex)
                self.unavailable_until = time.time() + 60
                raise RuntimeError("Mistral Rate Limit Exceeded")

            else:
                try:
                    body = response.text
                except Exception:
                    body = str(response)
                try:
                    from pathlib import Path
                    logs_dir = Path("logs")
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    fp = logs_dir / f"mistral_err_{int(time.time())}.json"
                    with fp.open("w", encoding="utf-8") as f:
                        f.write(body)
                    logger.error("Mistral API Error %s — body saved to %s", response.status_code, str(fp))
                except Exception as ex:
                    logger.error("Mistral API Error %s and failed to save body: %s", response.status_code, ex)
                raise RuntimeError(f"Mistral API Error: {response.status_code}")

        except Exception as e:
            logger.exception("Mistral request failed")
            raise RuntimeError(f"Mistral request failed: {e}")
