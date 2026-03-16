from __future__ import annotations

import json
import hashlib
import logging
import time
import random
import asyncio
from typing import Any, Optional

import requests

# Try to import official Google Generative AI SDK if present
try:
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

logger = logging.getLogger(__name__)


# Model names and limits (from provided context)
MAIN_MODEL = "gemini-3.1-flash-lite"  # primary
GEMMA_MODEL = "gemini-2.0-flash-lite"  # fallback for main on 429 and dedicated for intents (gemma-3-4b often 404s)
AUDIO_MODEL = "gemini-2.5-flash-tts"  # TTS/transcribe (limited)
EMBEDDING_MODEL = "gemini-embedding-2"

# Limits known from context (we'll use for local decisioning)
MODEL_LIMITS = {
    MAIN_MODEL: {"rpm": 15, "tpm": 250_000, "rpd": 500},
    GEMMA_MODEL: {"rpm": 30, "tpm": 15_000, "rpd": 14_400},
    AUDIO_MODEL: {"rpm": 3, "tpm": 10_000, "rpd": 10},
    EMBEDDING_MODEL: {"rpm": 100, "tpm": 30_000, "rpd": 1_000},
}


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
        self.base_url = self.settings.gemini_base_url.rstrip("/")
        # default models come from constants; config may override
        self.default_model = getattr(self.settings, 'gemini_model', None) or MAIN_MODEL
        self.intent_model = getattr(self.settings, 'gemini_intent_model', None) or GEMMA_MODEL
        self.audio_model = getattr(self.settings, 'gemini_audio_model', None) or AUDIO_MODEL
        self.embedding_model = EMBEDDING_MODEL
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
        """Синхронный helper, который выполняет requests.post с retry и возвращает json.
        Вызывать из async-кода через asyncio.to_thread, чтобы не блокировать loop.
        """
        if not self.enabled:
            raise RuntimeError("GEMINI_API_KEY не настроен")

        # Check temporary unavailability
        now_ts = time.time()
        disabled_until = self.unavailable_models.get(model)
        if disabled_until and now_ts < disabled_until:
            raise ModelUnavailableError(f"Model {model} is temporarily disabled until {disabled_until}")

        # If google SDK is available and configured, try it first (defensive)
        if self._use_google_sdk:
            try:
                if self.rate_limiter.would_exceed_rpd(model):
                    logger.debug("Rate limiter would exceed, skipping SDK attempt for model %s", model)
                else:
                    sdk_resp = self._sdk_generate(model, parts)
                    # treat as success: increment rate limiter and return
                    try:
                        self.rate_limiter.increment(model)
                    except Exception:
                        pass
                    return sdk_resp
            except ModelUnavailableError:
                # SDK indicated model unavailable (rethrow)
                raise
            except Exception as ex:
                logger.info("google.generativeai SDK attempt failed for model %s: %s — falling back to HTTP", model, ex)

        # Check local rate limiter before attempting
        if self.rate_limiter.would_exceed_rpd(model):
            # mark temporarily disabled for short cooldown to avoid repeated attempts
            self.unavailable_models[model] = time.time() + 60
            raise RuntimeError(f"Rate limit would be exceeded for model {model}")

        # We'll try multiple endpoint shapes and payload variants to be tolerant to API format differences
        prompt = "\n".join([p.get("text", "") for p in parts]).strip()

        endpoints = [
            (f"{self.base_url}/models/{model}:generateContent?key={self.api_key}", "contents_parts"),
            (f"{self.base_url}/models/{model}:generateText?key={self.api_key}", "input_text"),
            (f"{self.base_url}/models/{model}:generateMessage?key={self.api_key}", "messages"),
        ]

        payload_variants: list[dict[str, Any]] = []
        # original parts-style
        payload_variants.append({"contents": [{"parts": parts}]})
        # simple input/prompt text
        if prompt:
            payload_variants.append({"input": prompt})
            payload_variants.append({"prompt": prompt})
            # OpenAI-like messages
            payload_variants.append({"messages": [{"role": "user", "content": prompt}]})
            # Generative API 'messages' possible shape
            payload_variants.append({"messages": [{"author": "user", "content": [{"type": "text", "text": prompt}]}]})

        last_error: Exception | None = None
        # iterate attempts with exponential backoff
        for attempt in range(1, self.max_retries + 1):
            for url, shape in endpoints:
                for payload in payload_variants:
                    try:
                        logger.debug("Gemini trying URL %s with payload shape %s (attempt %s)", url, shape, attempt)
                        response = requests.post(url, json=payload, timeout=self.timeout)
                        # log non-2xx for diagnosis
                        if response.status_code >= 400:
                            logger.info("Gemini response status %s body: %s", response.status_code, response.text[:2000])
                        response.raise_for_status()
                        # increment RPD counter on success
                        try:
                            self.rate_limiter.increment(model)
                        except Exception:
                            pass
                        # clear any temporary disable state
                        if model in self.unavailable_models:
                            del self.unavailable_models[model]
                        return response.json()
                    except requests.HTTPError as ex:
                        last_error = ex
                        code = getattr(ex.response, "status_code", None)
                        logger.warning("Gemini request failed for url %s payload_shape %s on attempt %s: %s", url, shape, attempt, ex)
                        # If model not found (404) — treat as permanent-ish error, disable and abort
                        if code == 404:
                            logger.error("Model %s not found (404) at url %s. Aborting.", model, url)
                            self.unavailable_models[model] = time.time() + self._disable_404_seconds
                            raise ModelUnavailableError(f"Model {model} not found: {ex}")
                        if code == 429:
                            logger.warning("Model %s returned 429 at url %s; marking short cooldown.", model, url)
                            self.unavailable_models[model] = time.time() + self._cooldown_429_seconds
                            raise
                        # otherwise try next payload/endpoint
                        continue
                    except Exception as ex:
                        last_error = ex
                        logger.warning("Gemini network/transport error for url %s shape %s on attempt %s: %s", url, shape, attempt, ex)
                        # try next payload/endpoint
                        continue

            # backoff between attempts
            if attempt < self.max_retries:
                sleep_for = min(2 ** (attempt - 1), 8)
                sleep_for = sleep_for + random.uniform(0, 0.5)
                time.sleep(sleep_for)

        # exhausted attempts
        self.unavailable_models[model] = time.time() + self._cooldown_429_seconds
        raise RuntimeError(f"Gemini request failed after retries: {last_error}")

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

        primary = model or self.default_model or MAIN_MODEL

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
        intent_model = getattr(self, 'intent_model', GEMMA_MODEL)
        if primary != intent_model and model_available(intent_model):
            providers.append(("gemini", intent_model))
        else:
            if primary != intent_model:
                logger.debug("Skipping intent fallback model because unavailable or same as primary")

        # external providers (perplexity then openai) if allowed
        # Try OpenRouter first (free models) then Perplexity and OpenAI
        if self.openrouter.enabled and getattr(self.openrouter, 'can_call', None) and self.openrouter.can_call():
            providers.append(("openrouter", None))
        else:
            if self.openrouter.enabled:
                logger.debug("OpenRouter skipped (cooldown/unavailable)")

        if self.perplexity.enabled and getattr(self.perplexity, 'can_call', None) and self.perplexity.can_call():
            providers.append(("perplexity", None))
        else:
            if self.perplexity.enabled:
                logger.debug("Perplexity skipped (cooldown/unavailable)")

        if self.openai.enabled and getattr(self.openai, 'can_call', None) and self.openai.can_call():
            providers.append(("openai", None))
        else:
            if self.openai.enabled:
                logger.debug("OpenAI skipped (cooldown/unavailable)")

        if not providers:
            raise RuntimeError("No providers available to answer the request")

        last_error: Exception | None = None
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
                elif p_type == "perplexity":
                    response = await asyncio.to_thread(self.perplexity.generate_content, self._convert_to_openai_messages(all_parts))
                    text = self.perplexity.extract_text(response)
                    result = {"text": text, "raw": response, "tokens_used": self.estimate_tokens(text), "provider": "perplexity"}
                    break
                elif p_type == "openrouter":
                    response = await asyncio.to_thread(self.openrouter.generate_content, self._convert_to_openai_messages(all_parts))
                    text = self.openrouter.extract_text(response)
                    result = {"text": text, "raw": response, "tokens_used": self.estimate_tokens(text), "provider": "openrouter"}
                    break
                elif p_type == "openai":
                    response = await asyncio.to_thread(self.openai.generate_content, self._convert_to_openai_messages(all_parts))
                    text = self.openai.extract_text(response)
                    result = {"text": text, "raw": response, "tokens_used": self.estimate_tokens(text), "provider": "openai"}
                    break
            except ModelUnavailableError as mue:
                # mark that model in unavailable_models already done inside _post_generate_content_with_retries
                logger.info("Provider %s model %s unavailable: %s", p_type, p_model, mue)
                last_error = mue
                continue
            except Exception as ex:
                logger.warning("Provider %s failed: %s", p_type, ex)
                last_error = ex
                # if we receive rate-limit or auth error from external providers their services mark cooldown internally
                continue

        if not result:
            logger.error("All LLM attempts failed. Last error: %s", last_error)
            # Only return the local dev fallback if explicitly enabled
            if getattr(self.settings, 'assistant_force_local_llm', False):
                text = getattr(self.settings, 'assistant_local_llm_response', "(DEV) Внешние языковые сервисы недоступны — локальный ответ.")
                return {"text": text, "raw": None, "tokens_used": 0, "provider": "local"}
            # Default soft fallback message (no provider)
            return {
                "text": "Извините, все внешние языковые сервисы временно недоступны. Попробуйте повторить запрос через несколько минут.",
                "raw": None,
                "tokens_used": 0,
                "provider": "none",
            }

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
