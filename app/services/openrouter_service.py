from __future__ import annotations

import logging
from typing import Any, Optional
import requests
from datetime import datetime, timedelta, timezone
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class OpenRouterService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = getattr(self.settings, 'openrouter_api_key', '')
        # choose a free model by default (configurable)
        self.model = getattr(self.settings, 'openrouter_model', '')
        # Allowed free models (conservative list) — if configured model isn't in list, fallback to default
        self._allowed_free_models = {
            'gpt-3.5-mini',
            'gpt-3.5-small',
            'gpt-3.5-mini-rtl',
            'gpt-3.5-turbo-mini',
        }
        if self.model not in self._allowed_free_models:
            logger.warning("OpenRouter configured model '%s' is not in allowed free models; falling back to 'gpt-3.5-mini'", self.model)
            self.model = 'gpt-3.5-mini'
        # Candidate base URLs to try (order matters). Config can override primary via openrouter_base_url
        configured = getattr(self.settings, 'openrouter_base_url', '') or ''
        # Prefer the '/api' prefixed host first (correct path), then api.openrouter.ai
        candidates = [configured, 'https://openrouter.ai/api', 'https://api.openrouter.ai', 'https://openrouter.ai']
        # normalize and deduplicate while preserving order and removing empty strings
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

        # discover available models from the service (best-effort)
        self.available_models: list[str] = []
        if self.enabled:
            try:
                self._discover_models()
            except Exception as ex:
                logger.debug('OpenRouter model discovery failed: %s', ex)
        # If no explicit model configured, try to pick a free model
        if not self.model:
            for m in self.available_models:
                if ':free' in m or m.lower().startswith('google/') or 'gemma' in m.lower():
                    self.model = m
                    break
            # fallback to a safe default
            if not self.model:
                self.model = 'openai/gpt-3.5-turbo'

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

    def _mark_failure(self, status_code: Optional[int] = None):
        self.failure_count += 1
        self.last_failure = datetime.now(timezone.utc)
        # clear last_error will be set by caller
        # Only mark unhealthy after repeated failures
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
        # store last error info for debugging
        # (caller sets self.last_error before calling _mark_failure)

    def _try_post(self, payload: dict[str, Any], base_url: str, timeout: int = 20) -> dict[str, Any]:
        """Attempt a POST to a specific OpenRouter base_url. Raises requests exceptions on failure."""
        # Try both /api/v1/... and /v1/... variants depending on base_url
        candidates = []
        b = base_url.rstrip('/')
        # If base already contains '/api', prefer b + '/v1/...'
        if b.endswith('/api'):
            candidates.append(f"{b}/v1/chat/completions")
            candidates.append(f"{b[:-4]}/api/v1/chat/completions")
        else:
            candidates.append(f"{b}/api/v1/chat/completions")
            candidates.append(f"{b}/v1/chat/completions")
        headers = {
            # OpenRouter expects Authorization: Bearer <key>
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "quest-app/1.0"
        }
        last_exc: Exception | None = None
        for url in candidates:
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                text = resp.text or ""
                # If we get HTML body instead of JSON, try to detect known error pages (Model Not Found)
                if '<html' in text.lower() or text.strip().startswith('<!doctype'):
                    snippet = text[:4000]
                    logger.warning('OpenRouter returned HTML body for %s status=%s; snippet=%s', url, resp.status_code, snippet[:1000])
                    # detect Model Not Found page
                    if 'model not found' in text.lower() or '<title>model not found' in text.lower():
                        self.last_error = 'model_not_found'
                        self._mark_failure(status_code=resp.status_code)
                        return {"raw_text": snippet, "status_code": resp.status_code, "error": "model_not_found"}
                    # otherwise return raw html for debugging
                    return {"raw_text": snippet, "status_code": resp.status_code}
                # log non-2xx for diagnosis
                if resp.status_code >= 400:
                    logger.info('OpenRouter POST %s returned %s body=%s', url, resp.status_code, (text or '')[:2000])
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError:
                    return {"raw_text": text or "", "status_code": resp.status_code}
            except Exception as ex:
                last_exc = ex
                logger.debug('OpenRouter POST to %s failed: %s', url, ex)
                # try next candidate
                continue
        # if all candidates failed, re-raise last
        if last_exc:
            raise last_exc
        raise RuntimeError('OpenRouter POST failed for unknown reasons')

    def _messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        parts: list[str] = []
        for m in messages:
            # m may be {'role':..., 'content':...}
            c = m.get('content') if isinstance(m, dict) else m
            parts.append(str(c))
        return '\n'.join(parts).strip()

    def generate_content(self, messages: list[dict[str, str]], model: Optional[str] = None) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("OPENROUTER_API_KEY не настроен")
        if not self.can_call():
            raise RuntimeError("OpenRouter temporarily unavailable (cooldown)")

        model_to_use = model or self.model

        # prepare payload variants to try (in order)
        payloads: list[tuple[str, dict[str, Any]]] = []
        payloads.append(("messages", {"model": model_to_use, "messages": messages, "temperature": 0.2}))

        prompt = self._messages_to_prompt(messages)
        if prompt:
            payloads.append(("input_str", {"model": model_to_use, "input": prompt, "temperature": 0.2}))
            payloads.append(("input_list", {"model": model_to_use, "input": [{"role": "user", "content": prompt}], "temperature": 0.2}))
            payloads.append(("single_message", {"model": model_to_use, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}))
            payloads.append(("instances", {"model": model_to_use, "instances": [{"input": prompt}], "temperature": 0.2}))
            payloads.append(("prompt_field", {"model": model_to_use, "prompt": prompt, "temperature": 0.2}))

        last_exc: Optional[Exception] = None
        for name, payload in payloads:
            for base in self.base_urls:
                try:
                    logger.debug("OpenRouter trying variant '%s' with base '%s'", name, base)
                    result = self._try_post(payload, base_url=base)
                    # success
                    self.failure_count = 0
                    self.healthy = True
                    self.last_error = None
                    return result
                except requests.HTTPError as ex:
                    status = getattr(ex.response, 'status_code', None)
                    body = None
                    try:
                        body = ex.response.text
                    except Exception:
                        body = None
                    err_msg = f"base={base} status={status} body={body}"
                    logger.info("OpenRouter payload '%s' failed: %s", name, err_msg)
                    self.last_error = err_msg
                    last_exc = ex
                    if status and status != 400:
                        # non-400: mark failure and return
                        self._mark_failure(status_code=status)
                        if status == 401:
                            raise RuntimeError("OpenRouter API unauthorized (401). Check OPENROUTER_API_KEY")
                        if status == 429:
                            raise RuntimeError("OpenRouter rate limited (429). Try later")
                        # other non-400, break base loop to try next payload shape
                        break
                    # else continue to next base URL
                    continue
                except Exception as ex:
                    msg = str(ex)
                    logger.warning("OpenRouter attempt '%s' base '%s' failed: %s", name, base, msg)
                    self.last_error = msg
                    last_exc = ex
                    # If NameResolutionError in message, try next base URL; if all bases fail, treat as transient
                    if 'NameResolutionError' in msg or 'Failed to resolve' in msg or 'getaddrinfo failed' in msg:
                        # try next base URL
                        continue
                    # other transient network errors — try next base
                    continue
            # after iterating bases, if last_exc was non-HTTP or we exhausted bases for this payload, continue to next payload
            continue

        # All attempts exhausted: mark failure (use HTTP status if possible)
        if isinstance(last_exc, requests.HTTPError):
            status = getattr(last_exc.response, 'status_code', None)
            self._mark_failure(status_code=status)
        else:
            self._mark_failure()

        # raise the last exception for caller
        if last_exc:
            raise last_exc
        raise RuntimeError("OpenRouter request failed")

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

    def _discover_models(self) -> None:
        """Попытка получить список доступных моделей с OpenRouter и сохранить в self.available_models"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for base in self.base_urls:
            # try both /api/v1/models and /v1/models
            for path in ['/api/v1/models', '/v1/models']:
                url = f"{base.rstrip('/')}{path}"
                try:
                    resp = requests.get(url, headers=headers, timeout=10)
                    if resp.status_code != 200:
                        continue
                    data = None
                    try:
                        data = resp.json()
                    except ValueError:
                        continue
                    # OpenRouter returns {'data': [{'id': 'model-id', ...}, ...]}
                    items = data.get('data') or []
                    models = [it.get('id') for it in items if isinstance(it, dict) and it.get('id')]
                    self.available_models = models
                    logger.info('OpenRouter discovered %s models from %s', len(models), url)
                    return
                except Exception as ex:
                    logger.debug('OpenRouter model discovery failed for %s: %s', url, ex)
                    continue
        # if we reach here, no models discovered
        self.available_models = []

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
