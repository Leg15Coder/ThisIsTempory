from __future__ import annotations

import logging
from typing import Any, Optional
import requests
from datetime import datetime, timedelta, timezone
from app.core.config import get_settings
from app.services.model_rankings import get_models_for, update_rankings

logger = logging.getLogger(__name__)

class OpenRouterService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = getattr(self.settings, 'openrouter_api_key', '')
        # load ranked candidate models from rankings file
        ranked = get_models_for('openrouter') or []
        self.model = getattr(self.settings, 'openrouter_model', '') or (ranked[0] if ranked else '')
        self._allowed_free_models = set(ranked)

        # Candidate base URLs to try (order matters). Config can override primary via openrouter_base_url
        configured = getattr(self.settings, 'openrouter_base_url', '') or ''
        candidates = [configured, 'https://openrouter.ai/api', 'https://api.openrouter.ai', 'https://openrouter.ai']
        seen = set()
        self.base_urls: list[str] = []
        for u in candidates:
            if not u:
                continue
            u2 = u.rstrip('/')
            if u2 not in seen:
                seen.add(u2)
                self.base_urls.append(u2)
        if not self.base_urls:
            self.base_urls = ['https://api.openrouter.ai']

        # health/backoff
        self.healthy: bool = True
        self.failure_count: int = 0
        self.last_failure: Optional[datetime] = None
        self.last_error: Optional[str] = None
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

    def refresh_available_models(self) -> list[str]:
        """Best-effort method: try to fetch models list from OpenRouter and update rankings file.
        Returns the discovered list (may be empty on failure).
        """
        if not self.enabled:
            return []
        urls = [f"{b}/v1/models" for b in self.base_urls]
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for url in urls:
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    models = []
                    # Try various shapes
                    if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
                        for item in data['data']:
                            mid = item.get('id') or item.get('model')
                            if mid:
                                models.append(mid)
                    # fallback shapes
                    if not models and isinstance(data, list):
                        for item in data:
                            mid = item.get('id') if isinstance(item, dict) else None
                            if mid:
                                models.append(mid)
                    if models:
                        # update rankings by placing discovered free models at front if they are known
                        current = get_models_for('openrouter') or []
                        # merge keeping new models first
                        merged = models + [m for m in current if m not in models]
                        update_rankings({**{ 'openrouter': merged }})
                        self._allowed_free_models = set(merged)
                        self.model = merged[0]
                        return merged
            except Exception as ex:
                logger.debug("OpenRouter model discovery failed for %s: %s", url, ex)
                continue
        return []

    def _mark_failure(self, status_code: Optional[int] = None):
        self.failure_count += 1
        self.last_failure = datetime.now(timezone.utc)
        if status_code == 401:
            if self.failure_count >= 2:
                self.healthy = False
                logger.warning("OpenRouter marked unhealthy due to repeated 401 (auth). Cooldown %s seconds", self.auth_cooldown_seconds)
            else:
                logger.warning("OpenRouter received 401 (auth) — will mark unhealthy after repeated failures")
        elif status_code == 429:
            if self.failure_count >= 2:
                self.healthy = False
                logger.warning("OpenRouter marked transiently unhealthy due to repeated 429 (rate limit). Failure count %s", self.failure_count)
            else:
                logger.warning("OpenRouter rate limited (429) — will mark unhealthy after repeated failures")
        else:
            if self.failure_count >= 2:
                self.healthy = False
                logger.warning("OpenRouter marked transiently unhealthy due to repeated errors. Failure count %s", self.failure_count)
            else:
                logger.warning("OpenRouter transient error — will mark unhealthy after repeated failures. Failure count %s", self.failure_count)

    def _try_post(self, payload: dict[str, Any], base_url: str, timeout: int = 20) -> dict[str, Any]:
        """Attempt a POST to a specific OpenRouter base_url."""
        # Normalize base_url to ensure we end up with /api/v1/chat/completions
        url = base_url.rstrip('/')
        if url == 'https://openrouter.ai':
            url = 'https://openrouter.ai/api/v1/chat/completions'
        elif url == 'https://api.openrouter.ai':
            url = 'https://api.openrouter.ai/api/v1/chat/completions'
        elif url.endswith('/v1'):
             url = f"{url}/chat/completions"
        elif not url.endswith('/chat/completions'):
             # Assume base is e.g. .../api
             url = f"{url}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000",
            "X-OpenRouter-Title": "Quest App Assistant"
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            text = resp.text or ""
            # Handle HTML error pages — treat as failure and raise so LLM will fallback
            if '<html' in text.lower() or text.strip().startswith('<!doctype'):
                snippet = text[:1000]
                logger.warning('OpenRouter returned HTML for %s status=%s; snippet=%s', url, resp.status_code, snippet[:500])
                # Mark failure/backoff
                self._mark_failure(status_code=resp.status_code)
                # If indicates model not found, mark specific error
                if 'model not found' in text.lower():
                    self.last_error = 'model_not_found'
                    raise RuntimeError(f"OpenRouter model not found (HTML page) status={resp.status_code}")
                raise RuntimeError(f"OpenRouter returned HTML body (likely gateway or model page) status={resp.status_code}")

            if resp.status_code >= 400:
                logger.info('OpenRouter POST %s returned %s body=%s', url, resp.status_code, (text or '')[:500])
                self._mark_failure(status_code=resp.status_code)
                resp.raise_for_status()

            return resp.json()
        except Exception as ex:
            logger.debug('OpenRouter POST to %s failed: %s', url, ex)
            raise

    def _messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        parts: list[str] = []
        for m in messages:
            c = m.get('content') if isinstance(m, dict) else m
            parts.append(str(c))
        return '\n'.join(parts).strip()

    def generate_content(self, messages: list[dict[str, str]], model: Optional[str] = None) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("OPENROUTER_API_KEY не настроен")
        if not self.can_call():
            raise RuntimeError("OpenRouter temporarily unavailable (cooldown)")

        model_to_use = model or self.model or (next(iter(self._allowed_free_models)) if self._allowed_free_models else None)

        # Try models in order if model_to_use is a list, otherwise just primary
        models_to_try = []
        if isinstance(model_to_use, str):
            models_to_try = [model_to_use]
        elif isinstance(model_to_use, (list, tuple)):
            models_to_try = list(model_to_use)
        else:
            models_to_try = list(self._allowed_free_models) if self._allowed_free_models else ['openrouter/hunter-alpha']

        last_exc: Optional[Exception] = None

        # Iterate models, but only ONE request per model (except base_url fallback inside _try_post loop which is now simplified)
        for m in models_to_try:
            payload = {
                "model": m,
                "messages": messages,
                "max_tokens": 1024,
                "temperature": 0.7
            }

            # Try base URLs until one works
            for base in self.base_urls:
                try:
                    return self._try_post(payload, base_url=base)
                except Exception as ex:
                    last_exc = ex
                    continue

            # If failed for this model, maybe try next model
            self._mark_failure() # Mark general failure for rate limiting logic if needed

        if last_exc:
            raise last_exc
        raise RuntimeError("OpenRouter: no successful request")

    def extract_text(self, response: dict[str, Any]) -> str:
        # OpenRouter returns OpenAI-like responses
        if not response:
            return ""
        # response may be a dict with raw_text or OpenAI-like structure
        if isinstance(response, dict):
            if response.get('raw_text'):
                return str(response.get('raw_text') or "").strip()
            # some endpoints return {'choices':[{'message':{'content':...}}]}
            choices = response.get('choices') or []
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    return first.get('message', {}).get('content', '') or first.get('text', '') or ''
            # some services return {'data': [{'id':..., ...}], 'output': ...}
            if 'output' in response and isinstance(response['output'], str):
                return response['output'].strip()
            if 'text' in response and isinstance(response['text'], str):
                return response['text'].strip()
        if isinstance(response, str):
            return response.strip()
        return ""

    def reset_health(self):
        self.failure_count = 0
        self.healthy = True
        self.last_failure = None

    def get_status(self) -> dict[str, Any]:
        # compute remaining cooldown
        remaining = None
        if self.last_failure:
            elapsed = (datetime.now(timezone.utc) - self.last_failure).total_seconds()
            remaining = max(0, int(self.base_cooldown_seconds - elapsed))
        return {
            'enabled': self.enabled,
            'model': self.model,
            'can_call': self.can_call(),
            'failure_count': self.failure_count,
            'last_error': self.last_error,
            'cooldown_remaining_seconds': remaining,
        }
