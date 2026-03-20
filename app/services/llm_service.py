from __future__ import annotations

import asyncio
import logging
import json
from typing import Any, Optional

from app.core.config import get_settings
from app.models.assistant_models import AssistantMode, MemoryMessage
from app.services.gemini_service import GeminiService
from app.services.groq_service import GroqService
from app.services.mistral_service import MistralService
from app.services.zhipu_service import ZhipuService
from app.services.openrouter_service import OpenRouterService
from app.services.perplexity_service import PerplexityService
from app.services.openai_service import OpenAIService
from app.services.rate_limiter import get_rate_limiter
from app.services import token_utils
import time

logger = logging.getLogger(__name__)

class LLMService:
    """
    Centralized LLM service that orchestrates multiple providers with fallback logic.
    Prioritizes free/fast providers and falls back to others on failure.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

        # Initialize all providers
        self.gemini = GeminiService()
        self.groq = GroqService()
        self.mistral = MistralService()
        self.zhipu = ZhipuService()
        self.openrouter = OpenRouterService()
        self.perplexity = PerplexityService()
        self.openai = OpenAIService()

        # Default fallback order
        self.providers_order = [
            ("gemini", self.gemini),
            ("groq", self.groq),
            ("mistral", self.mistral),
            ("zhipu", self.zhipu),
            ("openrouter", self.openrouter),
            ("perplexity", self.perplexity),
            ("openai", self.openai),
        ]

        # Provider runtime status: track last_success, last_failure, failure_count
        now_ts = time.time()
        self.provider_status: dict[str, dict] = {}
        for name, _ in self.providers_order:
            self.provider_status[name] = {
                'last_success': 0.0,
                'last_failure': 0.0,
                'failure_count': 0,
            }

        # local rate limiter instance
        redis_url = getattr(self.settings, 'redis_url', None)
        self.rate_limiter = get_rate_limiter(redis_url=redis_url, rpm=getattr(self.settings, 'llm_rpm', 60), rpd=getattr(self.settings, 'llm_rpd', 1000))

    def _convert_to_openai_messages(self, prompt: str, system_prompt: Optional[str], context_messages: Optional[list[MemoryMessage]], summary: Optional[str]) -> list[dict[str, str]]:
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if summary:
            messages.append({"role": "system", "content": f"Summary of previous conversation: {summary}"})

        if context_messages:
            for msg in context_messages:
                role = msg.role if msg.role in ["user", "assistant", "system"] else "user"
                messages.append({"role": role, "content": msg.content})

        messages.append({"role": "user", "content": prompt})
        return messages

    def _extract_text_from_provider(self, provider_name: str, provider: object, response: dict[str, Any]) -> str:
        """Normalize extraction of text from various provider response shapes.
        Raises RuntimeError if the response is invalid or empty to trigger fallback.
        """
        if response is None:
            raise RuntimeError(f"{provider_name} returned no response")

        # If provider exposes extract_text helper use it
        if hasattr(provider, 'extract_text') and callable(getattr(provider, 'extract_text')):
            try:
                txt = provider.extract_text(response)
                if not txt or not str(txt).strip():
                    raise RuntimeError(f"{provider_name} returned empty text")
                # protect against HTML pages
                low = str(txt).lower()
                if '<html' in low or '<!doctype' in low:
                    raise RuntimeError(f"{provider_name} returned HTML page")
                return str(txt).strip()
            except Exception as e:
                raise RuntimeError(f"{provider_name} extraction failed: {e}")

        # Common OpenAI-style
        if isinstance(response, dict):
            # direct content field
            if 'content' in response and isinstance(response['content'], str) and response['content'].strip():
                txt = response['content'].strip()
                low = txt.lower()
                if '<html' in low or '<!doctype' in low:
                    raise RuntimeError(f"{provider_name} returned HTML in content")
                return txt

            # choices path
            choices = response.get('choices') or []
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    # try message.content
                    msg = first.get('message') or {}
                    if isinstance(msg, dict):
                        content = msg.get('content') or ''
                        if isinstance(content, str) and content.strip():
                            low = content.lower()
                            if '<html' in low or '<!doctype' in low:
                                raise RuntimeError(f"{provider_name} returned HTML in choices")
                            return content.strip()
                    # fallback text
                    text_choice = first.get('text') or ''
                    if isinstance(text_choice, str) and text_choice.strip():
                        low = text_choice.lower()
                        if '<html' in low or '<!doctype' in low:
                            raise RuntimeError(f"{provider_name} returned HTML in choices.text")
                        return text_choice.strip()

            # some providers return top-level 'text' or 'output'
            for key in ('text', 'output', 'raw_text'):
                if key in response and isinstance(response[key], str) and response[key].strip():
                    low = response[key].lower()
                    if '<html' in low or '<!doctype' in low:
                        raise RuntimeError(f"{provider_name} returned HTML in {key}")
                    return response[key].strip()

        # fallback: if response is str
        if isinstance(response, str) and response.strip():
            low = response.lower()
            if '<html' in low or '<!doctype' in low:
                raise RuntimeError(f"{provider_name} returned HTML string")
            return response.strip()

        raise RuntimeError(f"{provider_name} returned empty/unrecognized response")

    async def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: Optional[str] = None,
        context_messages: Optional[list[MemoryMessage]] = None,
        summary: Optional[str] = None,
        model: Optional[str] = None,  # Can be used to hint a specific model/provider
        response_mime_type: Optional[str] = None,
        max_tokens: int = 1024
    ) -> dict[str, Any]:

        # Prepare messages in standard format
        # Apply token-aware truncation/summarization before packaging messages
        try:
            context_limit = getattr(self.settings, 'assistant_context_token_budget', None) or 800
            # don't allow context budget exceed response max_tokens
            try:
                context_limit = min(context_limit, int(max_tokens))
            except Exception:
                pass
            use_summary_threshold = getattr(self.settings, 'assistant_summary_threshold_tokens', 1200)
            if context_messages:
                # estimate total tokens
                total_est = sum(token_utils.estimate_tokens(m.content or '') for m in context_messages)
                if total_est > use_summary_threshold:
                    summary = token_utils.summarize_context(context_messages, max_summary_tokens=200)
                    context_messages = token_utils.truncate_messages(context_messages, token_budget=context_limit)
                else:
                    context_messages = token_utils.truncate_messages(context_messages, token_budget=context_limit)
        except Exception as e:
            logger.debug('Context truncation/summarization failed: %s', e)

        messages = self._convert_to_openai_messages(prompt, system_prompt, context_messages, summary)

        last_error = None

        # Check dev override
        if getattr(self.settings, 'assistant_force_local_llm', False):
            return {
                "text": getattr(self.settings, 'assistant_local_llm_response', "(DEV) Local Response"),
                "raw": {},
                "provider": "local"
            }

        # Sort providers by dynamic health metrics to prefer healthy ones
        def _sort_key(item: tuple[str, object]) -> tuple:
            pname, prov = item
            st = self.provider_status.get(pname, {})
            enabled_score = 0 if getattr(prov, 'enabled', True) else 1
            failures = st.get('failure_count', 0)
            last_success = st.get('last_success', 0.0)
            last_failure = st.get('last_failure', 0.0)
            nowt = time.time()
            recent_failure_penalty = 1 if (nowt - last_failure) < max(30, failures * 10) else 0
            # sort by enabled, failures + penalty, prefer more recent success
            return (enabled_score, failures + recent_failure_penalty, -int(last_success))

        sorted_providers = sorted(self.providers_order, key=_sort_key)
        logger.debug("LLM providers order: %s", [p[0] for p in sorted_providers])

        # Iterate sequentially through providers, one attempt per provider
        for provider_name, provider in sorted_providers:
            # Skip disabled providers
            if not getattr(provider, 'enabled', True):
                logger.debug("Provider %s disabled, skipping", provider_name)
                continue

            # Provider-level availability checks
            if hasattr(provider, 'is_available') and not provider.is_available():
                logger.debug("Provider %s reported unavailable, skipping", provider_name)
                continue

            if hasattr(provider, 'can_call') and not provider.can_call():
                logger.debug("Provider %s cannot be called right now (cooldown), skipping", provider_name)
                continue

            # Determine a model hint for rate-limiting and concurrency keys
            try:
                model_hint = getattr(provider, 'default_model', None) or model or provider_name
            except Exception:
                model_hint = model or provider_name

            # Check RPD to avoid spamming provider
            try:
                if model_hint and self.rate_limiter.would_exceed_rpd(model_hint):
                    logger.warning("Rate limiter: would exceed RPD for model %s — skipping provider %s", model_hint, provider_name)
                    ps = self.provider_status.get(provider_name)
                    if ps is not None:
                        ps['failure_count'] = ps.get('failure_count', 0) + 1
                        ps['last_failure'] = time.time()
                    last_error = RuntimeError("Rate limit would be exceeded")
                    continue
            except Exception:
                logger.debug("Rate limiter check failed for %s — proceeding cautiously", provider_name)

            acquired = False
            try:
                # Try to reserve a concurrency slot for this model; skip if cannot
                acquired = self.rate_limiter.acquire_concurrency(model_hint, max_concurrent=getattr(self.settings, 'llm_max_concurrent', 6), timeout=2)
                if not acquired:
                    logger.warning("Concurrency slot unavailable for %s — skipping provider %s", model_hint, provider_name)
                    last_error = RuntimeError("Concurrency limit reached")
                    continue

                logger.info("Calling provider %s (model_hint=%s)", provider_name, model_hint)

                response_data = None

                if provider_name == "gemini":
                    parts = []
                    if system_prompt:
                        parts.append({"text": f"SYSTEM: {system_prompt}"})
                    if summary:
                        parts.append({"text": f"SUMMARY: {summary}"})
                    if context_messages:
                        ctx_str = "\n".join([f"{m.role}: {m.content}" for m in context_messages])
                        parts.append({"text": f"CONTEXT: {ctx_str}"})
                    parts.append({"text": prompt})

                    # Use provider's HTTP helper consistent with scripts examples
                    raw_resp = await asyncio.to_thread(provider._post_generate_content_with_retries, model or getattr(provider, 'default_model', None), parts)
                    response_data = raw_resp

                else:
                    # Generic providers: prefer generate_content, fallback to generate
                    if hasattr(provider, 'generate_content'):
                        response = await asyncio.to_thread(provider.generate_content, messages)
                        response_data = response
                    elif hasattr(provider, 'generate'):
                        response = await asyncio.to_thread(provider.generate, messages)
                        response_data = response
                    else:
                        raise RuntimeError(f"Provider {provider_name} has no callable generate method")

                # Normalize and validate text
                text_content = self._extract_text_from_provider(provider_name, provider, response_data)

                # If JSON mime requested, try to parse JSON safely
                if response_mime_type == "application/json":
                    try:
                        clean_text = text_content.replace("```json", "").replace("```", "").strip()
                        json_data = json.loads(clean_text)
                        # Successful JSON result
                        try:
                            self.rate_limiter.increment(model_hint, amount=1)
                        except Exception:
                            pass
                        # Update provider status
                        ps = self.provider_status.get(provider_name)
                        if ps is not None:
                            ps['last_success'] = time.time()
                            ps['failure_count'] = 0
                        return {"text": text_content, "json": json_data, "raw": response_data, "provider": provider_name}
                    except Exception as e:
                        logger.warning("Provider %s returned invalid JSON: %s", provider_name, e)
                        raise RuntimeError("Invalid JSON from provider")

                # Success path: increment counters and update provider health
                try:
                    self.rate_limiter.increment(model_hint, amount=1)
                except Exception:
                    pass

                ps = self.provider_status.get(provider_name)
                if ps is not None:
                    ps['last_success'] = time.time()
                    ps['failure_count'] = 0

                return {"text": text_content, "raw": response_data, "provider": provider_name}

            except Exception as e:
                logger.warning("Provider %s failed or returned invalid content: %s", provider_name, e)
                last_error = e
                # update provider status on failure
                try:
                    ps = self.provider_status.get(provider_name)
                    if ps is not None:
                        ps['failure_count'] = ps.get('failure_count', 0) + 1
                        ps['last_failure'] = time.time()
                except Exception:
                    pass
                # try to mark provider/model unavailable where supported
                try:
                    if hasattr(provider, 'unavailable_models') and isinstance(getattr(provider, 'unavailable_models'), dict):
                        provider.unavailable_models[model_hint or 'unknown'] = time.time() + 60
                except Exception:
                    pass
                # move to next provider
                continue

            finally:
                if acquired:
                    try:
                        self.rate_limiter.release_concurrency(model_hint)
                    except Exception:
                        pass

        # All providers exhausted
        logger.error("All providers failed. Last error: %s", last_error)
        return {"text": "Извините, сейчас я не могу ответить. Попробуйте позже.", "raw": {}, "provider": "none", "error": str(last_error)}

    async def generate_embeddings(self, text: str) -> list[float]:
        # Try Gemini, then others?
        # Zhipu also supports embeddings but I didn't implement it in the service class yet.
        # OpenRouter doesn't support embeddings standardly unless specific model.
        # So we stick with Gemini or fallback to logic.
        return await self.gemini.generate_embeddings(text)

    async def transcribe_audio(self, audio_base64: str, mime_type: str = "audio/webm") -> str:
        # Gemini supports audio
        try:
            return await self.gemini.transcribe_audio(audio_base64, mime_type)
        except Exception:
            # Groq implementation for audio? (Whisper) - not implemented in my class yet
            # For now just fail if Gemini fails
            logger.error("Audio transcription failed")
            return ""

    def get_system_prompt(self, mode: AssistantMode) -> str:
        # Delegate to Gemini service or config directly
        if mode == AssistantMode.PSYCH:
            return self.settings.psych_assistant_system_prompt
        return self.settings.fast_assistant_system_prompt
