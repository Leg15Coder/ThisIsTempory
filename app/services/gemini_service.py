from __future__ import annotations

import json
import hashlib
import logging
import time
import random
import asyncio
from typing import Any, Optional

import requests
import warnings

# Try to import official Google Generative AI SDK: prefer new `google.genai`, fallback to legacy `google.generativeai` while suppressing FutureWarning
genai = None
_GOOGLE_GENAI_AVAILABLE = False
try:
    import google.genai as genai
    _GOOGLE_GENAI_AVAILABLE = True
except Exception:
    genai = None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=FutureWarning)
            import google.generativeai as genai
            _GOOGLE_GENAI_AVAILABLE = True
    except Exception:
        genai = None
        _GOOGLE_GENAI_AVAILABLE = False

from app.core.config import get_settings
from app.models.assistant_models import AssistantMode, MemoryMessage
from app.services.rate_limiter import get_rate_limiter
from app.services.perplexity_service import PerplexityService
from app.services.openai_service import OpenAIService
from app.services.openrouter_service import OpenRouterService
from app.services.model_rankings import get_models_for, update_rankings, load_rankings

logger = logging.getLogger(__name__)


class ModelUnavailableError(RuntimeError):
    """Raised when a requested model is not available (HTTP 404)"""
    pass


class GeminiService:
    """Обёртка над Gemini API с каскадной стратегией, retry/jitter и учётом RPD.

    Стратегия:
    - По умолчанию используем MAIN_MODEL.
    - При 429 на MAIN_MODEL делаем fallback на GEMMA_MODEL.
    - При дальнейших ошибках (или если Gemma недоступна) — fallback на Perplexity -> OpenAI.
    - Retry: экспоненциальный backoff с случайным джиттером.
    - Интеграция с RateLimiter: считаем RPD и даём возможность проверить перед вызовом.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.gemini_api_key
        # safe base_url handling: settings may be empty — default to Google's public endpoint used in scripts
        configured_base = getattr(self.settings, 'gemini_base_url', '') or ''
        if configured_base:
            self.base_url = configured_base.rstrip('/')
        else:
            self.base_url = 'https://generativelanguage.googleapis.com'
        # default models come from constants; config may override. Default to the working example model
        self.default_model = getattr(self.settings, 'gemini_model', None) or 'gemini-2.5-flash'
        self.intent_model = getattr(self.settings, 'gemini_intent_model', None)
        self.audio_model = getattr(self.settings, 'gemini_audio_model', None)
        self.embedding_model = "gemini-embedding-2"
        self.timeout = getattr(self.settings, "gemini_timeout_seconds", 30)
        self.max_retries = getattr(self.settings, "gemini_max_retries", 3)
        # use local rate limiter instance (optionally backed by redis if REDIS_URL provided)
        redis_url = getattr(self.settings, "redis_url", None)
        # conservative internal limits (90% of declared user limits)
        self.rate_limiter = get_rate_limiter(redis_url=redis_url, rpm=12, rpd=450)

        # Fallback services
        self._perplexity = None
        self._openai = None
        self._openrouter = None

        # temporary unavailability map: model -> unix ts until which it is disabled
        self.unavailable_models: dict[str, float] = {}
        self._disable_404_seconds = getattr(self.settings, 'gemini_model_disable_404_seconds', 3600)
        self._cooldown_429_seconds = getattr(self.settings, 'gemini_model_cooldown_429_seconds', 60)

        # Google SDK usage flag
        self._use_google_sdk = _GOOGLE_GENAI_AVAILABLE and bool(self.api_key)
        if self._use_google_sdk:
            try:
                # configure SDK if available
                if hasattr(genai, 'configure'):
                    try:
                        genai.configure(api_key=self.api_key)
                        logger.info("google.generativeai SDK configured for GeminiService")
                    except Exception as ex:
                        logger.warning("Failed to configure google.generativeai SDK: %s", ex)
                else:
                    logger.info("google.generativeai imported but has no configure() method; will attempt reflective calls")
            except Exception as ex:
                logger.warning("google.generativeai present but failed during init: %s", ex)
                self._use_google_sdk = False

        # Load initial model rankings from file (do not overwrite file here)
        ranked = get_models_for('gemini') or []
        # prefer explicit settings, otherwise fall back to rankings
        if not self.default_model:
            self.default_model = ranked[0] if ranked else None
        if not self.intent_model:
            # try to pick a light/cheap model for intents
            candidate = None
            for r in ranked:
                if 'gemma' in r or 'lite' in r or '2.0' in r:
                    candidate = r
                    break
            self.intent_model = candidate or (ranked[1] if len(ranked) > 1 else None)
        if not self.audio_model:
            # prefer models with tts in name
            candidate = None
            for r in ranked:
                if 'tts' in r or 'audio' in r or 'speech' in r:
                    candidate = r
                    break
            self.audio_model = candidate

        # embedding model from settings or sensible default
        self.embedding_model = getattr(self.settings, 'gemini_embedding_model', self.embedding_model)

        # attempt to refresh models list from remote (best-effort)
        try:
            self.refresh_available_models()
        except Exception:
            logger.debug('Gemini refresh_available_models failed during init, continuing with local rankings')

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def perplexity(self) -> PerplexityService:
        if not self._perplexity:
            self._perplexity = PerplexityService()
        return self._perplexity

    @property
    def openai(self) -> OpenAIService:
        if not self._openai:
            self._openai = OpenAIService()
        return self._openai

    @property
    def openrouter(self) -> OpenRouterService:
        if not self._openrouter:
            self._openrouter = OpenRouterService()
        return self._openrouter

    def estimate_tokens(self, text: str) -> int:
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

    def _post_generate_content_with_retries(self, model: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
        """Синхронный helper, который выполняет requests.post с retry и возвращает json."""
        if not self.enabled:
            raise RuntimeError("GEMINI_API_KEY не настроен")

        # Check temporary unavailability
        now_ts = time.time()
        disabled_until = self.unavailable_models.get(model)
        if disabled_until and now_ts < disabled_until:
            raise ModelUnavailableError(f"Model {model} is temporarily disabled until {disabled_until}")

        # If google SDK is available and configured, try it first
        if self._use_google_sdk:
            try:
                if self.rate_limiter.would_exceed_rpd(model):
                    logger.debug("Rate limiter would exceed, skipping SDK attempt for model %s", model)
                else:
                    sdk_resp = self._sdk_generate(model, parts)
                    try:
                        self.rate_limiter.increment(model)
                    except Exception:
                        pass
                    return sdk_resp
            except ModelUnavailableError:
                raise
            except Exception as ex:
                logger.info("google.generativeai SDK attempt failed: %s — falling back to HTTP", ex)

        # Check local rate limiter
        if self.rate_limiter.would_exceed_rpd(model):
            self.unavailable_models[model] = time.time() + 60
            raise RuntimeError(f"Rate limit exceeded for model {model}")

        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "maxOutputTokens": 1024,
                "temperature": 0.7
            }
        }

        # Single retry loop for network errors or transient 5xx
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url=url,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(payload),
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    try:
                        self.rate_limiter.increment(model)
                    except Exception:
                        pass
                    # clear unavailability if successful
                    if model in self.unavailable_models:
                        del self.unavailable_models[model]
                    return response.json()

                if response.status_code == 429:
                    # Save the full body to a local file (do not print huge JSON to console)
                    try:
                        body = response.text if hasattr(response, 'text') else str(response)
                    except Exception:
                        body = str(response)
                    ts = int(time.time())
                    try:
                        from pathlib import Path
                        logs_dir = Path("logs")
                        logs_dir.mkdir(parents=True, exist_ok=True)
                        file_path = logs_dir / f"gemini_429_{model}_{ts}.json"
                        with file_path.open("w", encoding="utf-8") as f:
                            f.write(body)
                        logger.warning("Gemini 429 for %s — body saved to %s (truncated in console)", model, str(file_path))
                    except Exception as ex:
                        logger.warning("Gemini 429 for %s — failed to write body to file: %s", model, ex)
                    # mark model unavailable for cooldown period
                    self.unavailable_models[model] = time.time() + self._cooldown_429_seconds
                    # raise a concise error (caller can inspect saved file if needed)
                    raise RuntimeError(f"Gemini 429 Too Many Requests for {model}. Body saved to {str(file_path) if 'file_path' in locals() else 'N/A'}")

                if response.status_code == 404:
                    self.unavailable_models[model] = time.time() + self._disable_404_seconds
                    raise ModelUnavailableError(f"Gemini Model {model} not found (404)")

                if 500 <= response.status_code < 600:
                    logger.warning(f"Gemini 5xx error {response.status_code}, attempt {attempt+1}")
                    time.sleep(1 + random.random())
                    continue

                raise RuntimeError(f"Gemini API Error {response.status_code}: {response.text}")

            except requests.RequestException as e:
                logger.warning(f"Gemini network error attempt {attempt+1}: {e}")
                time.sleep(1 + random.random())
                continue

        raise RuntimeError("Gemini max retries exhausted")

    def _extract_text(self, data: dict[str, Any]) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        return "\n".join(text_parts).strip()

    def _convert_to_openai_messages(self, parts: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Преобразует формат Gemini parts в формат сообщений OpenAI/Perplexity"""
        messages = []
        system_text = ""
        user_text = ""
        context_text = ""

        for part in parts:
            text = part.get("text", "")
            if text.startswith("SYSTEM:"):
                system_text += text[7:].strip() + "\n"
            elif text.startswith("CONTEXT:"):
                context_text += text[8:].strip() + "\n"
            else:
                user_text += text + "\n"

        if system_text:
            messages.append({"role": "system", "content": system_text.strip()})

        final_user_content = ""
        if context_text:
            final_user_content += f"Context:\n{context_text}\n"
        final_user_content += user_text

        messages.append({"role": "user", "content": final_user_content.strip()})
        return messages

    async def _fallback_to_external_providers(self, all_parts: list[dict[str, Any]]) -> dict[str, Any]:
        """Попытка использовать Perplexity, затем OpenAI"""
        messages = self._convert_to_openai_messages(all_parts)

        # 1. Try Perplexity if allowed
        if self.perplexity.enabled and getattr(self.perplexity, 'can_call', None) and self.perplexity.can_call():
            logger.info("Attempting fallback to Perplexity...")
            try:
                response = await asyncio.to_thread(self.perplexity.generate_content, messages)
                text = self.perplexity.extract_text(response)
                return {
                    "text": text,
                    "raw": response,
                    "tokens_used": self.estimate_tokens(text),
                    "provider": "perplexity"
                }
            except Exception as ex:
                logger.warning("Perplexity fallback failed: %s", ex)
        else:
            if self.perplexity.enabled:
                logger.info("Perplexity is in cooldown/unavailable, skipping.")

        # 2. Try OpenAI if allowed
        if self.openai.enabled and getattr(self.openai, 'can_call', None) and self.openai.can_call():
            logger.info("Attempting fallback to OpenAI...")
            try:
                response = await asyncio.to_thread(self.openai.generate_content, messages)
                text = self.openai.extract_text(response)
                return {
                    "text": text,
                    "raw": response,
                    "tokens_used": self.estimate_tokens(text),
                    "provider": "openai"
                }
            except Exception as ex:
                logger.warning("OpenAI fallback failed: %s", ex)
        else:
            if self.openai.enabled:
                logger.info("OpenAI is in cooldown/unavailable, skipping.")

        raise RuntimeError("All fallback providers failed")

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
        result: dict[str, Any] = {}
        all_parts: list[dict[str, Any]] = []
        if system_prompt:
            all_parts.append({"text": f"SYSTEM:\n{system_prompt.strip()}"})
        if context_messages:
            context_text = self.build_context_text(context_messages, summary=summary)
            if context_text:
                all_parts.append({"text": f"CONTEXT:\n{context_text}"})
        all_parts.append({"text": prompt.strip()})

        primary = model or self.default_model or "gemini-3.1-flash-lite"

        # Dev: forced local LLM fallback
        if getattr(self.settings, 'assistant_force_local_llm', False):
            logger.info("assistant_force_local_llm enabled — returning local fallback response")
            return {
                "text": getattr(self.settings, 'assistant_local_llm_response', "(DEV) LLM temporarily unavailable."),
                "raw": None,
                "tokens_used": 0,
                "provider": "local",
            }

        # Build ordered providers list respecting temporary disable flags and external can_call
        now_ts = time.time()
        providers = []  # tuples (provider_type, model_name)

        def model_available(m_name: str) -> bool:
            until = self.unavailable_models.get(m_name)
            return not (until and now_ts < until)

        # primary Gemini model
        if model_available(primary):
            providers.append(("gemini", primary))
        else:
            logger.debug("Skipping primary model %s because it is temporarily unavailable", primary)

        # internal fallback intent model (Gemma or configured fallback) if different and available
        intent_model = getattr(self, 'intent_model', "gemini-2.0-flash-lite")
        if primary != intent_model and model_available(intent_model):
            providers.append(("gemini", intent_model))
        else:
            if primary != intent_model:
                logger.debug("Skipping intent fallback model because unavailable or same as primary")

        # We intentionally DO NOT fallback to external providers here (openrouter/perplexity/openai)
        # so that orchestration layer (LLMService) controls the global provider order (including groq, zhipu, mistral, etc.).
        # Only try the primary and intent Gemini models here.
        last_error: Exception | None = None
        # primary attempt already appended above if available
        for p_type, p_model in providers:
            try:
                if p_type == "gemini":
                    raw = await asyncio.to_thread(self._post_generate_content_with_retries, p_model, all_parts)
                    text = self._extract_text(raw)
                    usage_text = "\n".join(part.get("text", "") for part in all_parts)
                    result = {
                        "text": text,
                        "raw": raw,
                        "tokens_used": self.estimate_tokens(usage_text) + self.estimate_tokens(text),
                        "provider": "gemini" if p_model == self.default_model else "gemini-intent",
                    }
                    break
            except ModelUnavailableError as mue:
                logger.info("Gemini model %s unavailable: %s", p_model, mue)
                last_error = mue
                continue
            except Exception as ex:
                logger.warning("Gemini model %s failed: %s", p_model, ex)
                last_error = ex
                continue

        if not result:
            # Let LLMService handle external fallback ordering — raise to indicate gemini could not produce an answer
            raise RuntimeError(f"Gemini failed for models; last_error={last_error}")

        if response_mime_type == "application/json":
            parsed_json: dict[str, Any] | None
            try:
                text_content = result.get("text", "")
                clean_text = text_content.replace("```json", "").replace("```", "").strip()
                parsed_json = json.loads(clean_text)
            except Exception:
                parsed_json = None
            result["json"] = parsed_json

        return result

    async def transcribe_audio(self, audio_base64: str, mime_type: str = "audio/webm") -> str:
        # Only attempt audio if TTS model has remaining RPD capacity
        if self.rate_limiter.would_exceed_rpd(self.audio_model):
            raise RuntimeError("Audio TTS capacity exceeded for today")

        prompt = "Преобразуй аудио в точный текст на русском языке. Верни только распознанный текст без комментариев."
        try:
            raw = await asyncio.to_thread(self._post_generate_content_with_retries, self.audio_model, [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": audio_base64}},
            ])
        except Exception as ex:
            logger.warning("Audio model call failed: %s", ex)
            # fallback to gemma text mode? gemma may not accept audio — so fail gracefully
            raise
        text = self._extract_text(raw)
        return text.strip()

    async def generate_embeddings(self, text: str, model: Optional[str] = None) -> list[float] | None:
        """Попытаться получить эмбеддинг через Gemini embedding модель.
        Если запрос не удался — вернуть детерминированный псевдо-вектор (fallback).
        """
        if not text:
            return None
        model = model or self.embedding_model
        if not self.enabled:
            return None

        url = f"{self.base_url}/models/{model}:embed?key={self.api_key}"
        payload = {"input": [text]}
        try:
            resp = await asyncio.to_thread(requests.post, url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            # ожидаем, что ответ содержит 'embeddings' или похожую структуру
            # Попробуем найти в разных вариантах
            embeddings = None
            if isinstance(data, dict):
                if 'embeddings' in data:
                    embeddings = data['embeddings']
                elif 'data' in data and isinstance(data['data'], list) and len(data['data']) and isinstance(data['data'][0], dict):
                    embeddings = data['data'][0].get('embedding') or data['data'][0].get('embeddings')
            if embeddings and isinstance(embeddings, list):
                # если embeddings — список списков, берем первый
                if embeddings and isinstance(embeddings[0], list):
                    return embeddings[0]
                # если embeddings — плоский список
                return embeddings
        except Exception as ex:
            logger.debug("Embedding request failed: %s", ex)

        # Fallback: deterministic pseudo-embedding from sha256
        h = hashlib.sha256(text.encode('utf-8')).digest()
        vec = [b / 255.0 for b in h]
        # expand or shrink to 64-dim
        if len(vec) < 64:
            vec = (vec * (64 // len(vec) + 1))[:64]
        return vec[:64]

    def get_system_prompt(self, mode: AssistantMode) -> str:
        if mode == AssistantMode.PSYCH:
            return self.settings.psych_assistant_system_prompt
        return self.settings.fast_assistant_system_prompt

    def get_status(self) -> dict[str, Any]:
        """Вернуть текущее состояние провайдеров и временно отключённых моделей (для отладки).
        Формат: { 'gemini': { 'enabled': bool }, 'perplexity': { 'enabled': bool, 'can_call': bool, ... }, 'openai': {...}, 'unavailable_models': {...} }
        """
        status = {
            "gemini": {"enabled": self.enabled, "default_model": self.default_model},
            "perplexity": {"enabled": self.perplexity.enabled, "can_call": getattr(self.perplexity, 'can_call', lambda: True)()},
            "openai": {"enabled": self.openai.enabled, "can_call": getattr(self.openai, 'can_call', lambda: True)()},
            "openrouter": {"enabled": self.openrouter.enabled, "can_call": getattr(self.openrouter, 'can_call', lambda: True)()},
            "unavailable_models": {},
        }
        now_ts = time.time()
        for m, until_ts in list(self.unavailable_models.items()):
            remaining = max(0, int(until_ts - now_ts))
            status["unavailable_models"][m] = remaining
        return status

    def _sdk_generate(self, model: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
        """Attempt to generate text using the official google.generativeai SDK when available.
        This function is defensive: it tries several known call patterns and returns a dict
        compatible with existing _extract_text expectations (candidates/content/parts).
        If SDK calls fail or API surface differs, it raises the underlying exception
        so the HTTP fallback can be attempted by caller.
        """
        if not self._use_google_sdk:
            raise RuntimeError("Google Generative AI SDK not available")

        # combine parts into a single prompt string (the SDK usually accepts text input)
        prompt = "\n".join(p.get("text", "") for p in parts)

        # Try several known SDK call styles defensively
        try:
            # Newer client: genai.models.generate(model=model, input=prompt)
            models_obj = getattr(genai, 'models', None)
            if models_obj and hasattr(models_obj, 'generate'):
                resp = models_obj.generate(model=model, input=prompt)
                # try to extract text from common shapes
                # If resp has .candidates or .outputs, wrap accordingly
                try:
                    # If resp is a mapping-like
                    if isinstance(resp, dict):
                        return resp
                    # Some SDKs return objects with .text or .output
                    text_val = getattr(resp, 'text', None) or getattr(resp, 'output', None)
                    if text_val:
                        return {'candidates': [{'content': {'parts': [{'text': str(text_val)}]}}]}
                except Exception:
                    return {'candidates': [{'content': {'parts': [{'text': str(resp)}]}}]}

            # Older/simple helper: genai.generate_text(model=model, prompt=prompt)
            if hasattr(genai, 'generate_text'):
                maybe = genai.generate_text(model=model, prompt=prompt)
                # maybe is a dict or object
                if isinstance(maybe, dict):
                    return maybe
                txt = getattr(maybe, 'text', None) or getattr(maybe, 'output', None) or str(maybe)
                return {'candidates': [{'content': {'parts': [{'text': str(txt)}]}}]}

            # Fallback: try genai.generate(model=model, prompt=prompt)
            if hasattr(genai, 'generate'):
                maybe = genai.generate(model=model, prompt=prompt)
                if isinstance(maybe, dict):
                    return maybe
                txt = getattr(maybe, 'text', None) or getattr(maybe, 'output', None) or str(maybe)
                return {'candidates': [{'content': {'parts': [{'text': str(txt)}]}}]}

            raise RuntimeError('No supported call pattern found on google.generativeai')
        except Exception:
            # Re-raise to let caller fall back to HTTP implementation
            raise

    def refresh_available_models(self):
        """Attempt to fetch available models from Gemini endpoints and update local rankings file.
        Best-effort; on failure leaves existing rankings intact.
        """
        logger.info("Refreshing available Gemini models from API...")
        if not self.enabled:
            logger.debug("Gemini API key not configured; skipping refresh")
            return []

        endpoints = []
        # try v1beta then v1
        if self.base_url:
            endpoints.append(f"{self.base_url}/v1beta/models?key={self.api_key}")
            endpoints.append(f"{self.base_url}/v1/models?key={self.api_key}")
        else:
            endpoints.append(f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}")
            endpoints.append(f"https://generativelanguage.googleapis.com/v1/models?key={self.api_key}")

        discovered = []
        for url in endpoints:
            try:
                resp = requests.get(url, timeout=8)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                # possible shapes: {'models': [...]} or {'models': [{'name':...}]}
                if isinstance(data, dict):
                    models_list = data.get('models') or data.get('data') or []
                    for item in models_list:
                        # item may be string or dict with 'name' or 'model' key
                        if isinstance(item, str):
                            discovered.append(item)
                        elif isinstance(item, dict):
                            mid = item.get('name') or item.get('id') or item.get('model')
                            if mid:
                                discovered.append(mid)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            mid = item.get('name') or item.get('id') or item.get('model')
                            if mid:
                                discovered.append(mid)
                if discovered:
                    break
            except Exception as ex:
                logger.debug('Gemini discovery attempt failed for %s: %s', url, ex)
                continue

        # merge with existing rankings
        try:
            current = get_models_for('gemini') or []
            merged = discovered + [m for m in current if m not in discovered]
            if merged:
                # preserve other provider rankings
                existing = load_rankings() or {}
                existing['gemini'] = merged
                update_rankings(existing)
                # update local pointers if not set
                if not self.default_model:
                    self.default_model = merged[0]
                if not self.intent_model and len(merged) > 1:
                    self.intent_model = merged[1]
                return merged
        except Exception as ex:
            logger.debug('Failed to merge/update gemini model rankings: %s', ex)

        return []
