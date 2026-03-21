from __future__ import annotations

import json
import logging
import time
import random
import asyncio
from typing import Any, Optional, override
from pathlib import Path

import requests
from requests import Response

from app.models.assistant_models import MemoryMessage
from app.services.llm_services.base_llm_service import BaseLLMService, ModelTypes
from app.services.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


class ModelUnavailableError(RuntimeError):
    """Raised when a requested model is not available (HTTP 404)"""
    pass


class GeminiService(BaseLLMService):
    def __init__(self) -> None:
        super().__init__()
        self.api_key = self.settings.gemini_api_key
        self.timeout = getattr(self.settings, "gemini_timeout_seconds", 30)
        self.max_retries = getattr(self.settings, "gemini_max_retries", 3)
        redis_url = getattr(self.settings, "redis_url", None)
        self.rate_limiter = get_rate_limiter(redis_url=redis_url, rpm=12, rpd=450)

        current_dir = Path(__file__).parent
        rankings_file = current_dir / 'model_rankings.json'

        if not rankings_file.exists():
            raise RuntimeError()

        with open(rankings_file, 'r', encoding='utf-8') as f:
            rankings = json.load(f)
            self.models = rankings.get('gemini', None)
            if self.models is None:
                logger.warning("Модели Gemini не подгружены")
                self.api_key = None

        self.unavailable_models: dict[str, float] = {}
        self._disable_404_seconds = getattr(self.settings, 'gemini_model_disable_404_seconds', 3600)
        self._cooldown_429_seconds = getattr(self.settings, 'gemini_model_cooldown_429_seconds', 60)

    def __del__(self) -> None:
        current_dir = Path(__file__).parent  # app/services/llm_services/
        rankings_file = current_dir / 'model_rankings_new.json'

        if not rankings_file.exists():
            raise RuntimeError()

        with open(rankings_file, 'w', encoding='utf-8') as f:
            rankings = json.load(f)
            rankings['gemini'] = self.models
            json.dump(rankings, f, indent=2, ensure_ascii=False)

    @override
    def craft_url(self, model: str) -> str:
        return f'https://generativelanguage.googleapis.com/v1beta/models/{model}?key={self.api_key}'

    def save_response_to_logs(self, model: str, response: Response) -> None:
        if self.settings.debug:
            try:
                ts = int(time.time())
                logs_dir = Path("logs")
                logs_dir.mkdir(parents=True, exist_ok=True)
                file_path = logs_dir / f"gemini_{response.status_code}_{model}_{ts}.json"
                with file_path.open("w", encoding="utf-8") as f:
                    f.write(response.json())
            except Exception as ex:
                logger.debug("Не удалось сохранить в логи модель %s: %s", model, ex)

    @override
    def get_next_model(self, model_type: ModelTypes) -> Optional[str]:
        models = self.models[model_type.value]
        if not models:
            return None

        best_model = max(models, key=lambda x: models[x])
        self.models[model_type.value][best_model] *= 0.5
        return best_model

    @override
    def update_model(self, model: str, weight: float = 2.01) -> None:
        for category in self.models:
            if model in category:
                self.models[category][model] *= weight
                return

    def _post_generate_content_with_retries(self, model: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
        """Синхронный helper, который выполняет requests.post с retry и возвращает json."""
        if not self.enabled:
            raise RuntimeError("GEMINI_API_KEY не настроен")

        now_ts = time.time()
        disabled_until = self.unavailable_models.get(model)
        if disabled_until and now_ts < disabled_until:
            raise ModelUnavailableError(f"Модель {model} временно приостановлена до {disabled_until}")

        if self.rate_limiter.would_exceed_rpd(model):
            self.unavailable_models[model] = time.time() + 60
            raise RuntimeError(f"Rate limit exceeded for model {model}")

        url = self.craft_url(model)
        payload = self.craft_payload(parts)

        try:
            response = requests.post(
                url=url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=self.timeout
            )

            self.save_response_to_logs(model, response)

            if response.status_code == 200:
                try:
                    self.rate_limiter.increment(model)
                except Exception as ex:
                    logger.warning("Ошибка RateLimiter при инкременте после успешного ответа: %s", ex)

                if model in self.unavailable_models:
                    del self.unavailable_models[model]
                return response.json()

            if response.status_code == 429:
                self.unavailable_models[model] = time.time() + self._cooldown_429_seconds
                raise ModelUnavailableError(f"Gemini {model} слишком много запросов (429). Модель временно приостановлена.")

            if response.status_code == 404:
                self.unavailable_models[model] = time.time() + self._disable_404_seconds
                raise ModelUnavailableError(f"Gemini {model} не найден (404). Модель временно приостановлена.")

            if 500 <= response.status_code < 600:
                logger.warning(f"Gemini 5xx ошибка: {response.status_code}")
                time.sleep(1 + random.random())

                raise RuntimeError(f"Ошибка Gemini API {response.status_code}: {response.text}")

        except requests.RequestException as e:
            logger.warning(f"Ошибка сети в сервисе Gemini: {e}")
            time.sleep(1 + random.random())

        raise RuntimeError("Gemini исчерпал все попытки запроса.")

    def __model_available(self, m_name: str) -> bool:
        until = self.unavailable_models.get(m_name)
        return not (until and time.time() < until)

    @override
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context_messages: Optional[list[MemoryMessage]] = None,
        summary: Optional[str] = None,
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

        if getattr(self.settings, 'assistant_force_local_llm', False):
            logger.info("assistant_force_local_llm включен — возврат локального ответа без вызова API")
            return {
                "text": getattr(self.settings, 'assistant_local_llm_response', "(DEV) LLM temporarily unavailable."),
                "raw": None,
                "tokens_used": 0,
                "provider": "local",
            }

        attempt = 0
        last_error: Exception | None = None

        while attempt < self.max_retries:
            attempt += 1
            model = self.get_next_model(ModelTypes.TEXT)

            if not self.__model_available(model):
                logger.debug("Пропущена модель %s потому что она временно недоступна", model)

            try:
                raw = await asyncio.to_thread(self._post_generate_content_with_retries, model, all_parts)
                text = self._extract_text(raw)
                usage_text = "\n".join(part.get("text", "") for part in all_parts)
                result = {
                    "text": text,
                    "raw": raw,
                    "tokens_used": self.estimate_tokens(usage_text) + self.estimate_tokens(text),
                    "provider": "gemini",
                }
                self.update_model(model)
                break
            except ModelUnavailableError as mue:
                logger.info("Модель %s недоступна: %s", model, mue)
                last_error = mue
                self.update_model(model, 1.8)
                continue
            except Exception as ex:
                logger.warning("Модель %s вернула ошибку: %s", model, ex)
                last_error = ex
                continue

        if not result:
            raise RuntimeError(f"Gemini не вернула ответ ни на один запрос; last_error={last_error}")

        if response_mime_type == "application/json":
            parsed_json: dict[str, Any] | None
            try:
                text_content = result.get("text", "")
                clean_text = text_content.replace("```json", "").replace("```", "").strip()
                parsed_json = json.loads(clean_text)
            except Exception as ex:
                parsed_json = None
                logger.warning("Не удалось распарсить JSON из ответа Gemini: %s", ex)
            result["json"] = parsed_json

        return result

    @override
    async def generate_embeddings(self, text: str, model: Optional[str] = None) -> list[float] | None:
        """Попытаться получить эмбеддинг через Gemini embedding модель.
        Если запрос не удался — вернуть детерминированный псевдо-вектор (fallback).
        """
        if not text or not self.enabled:
            return None

        model = model or self.get_next_model(ModelTypes.EMBEDDING)
        url = self.craft_url(model)
        payload = {"input": [text]}
        text = text[:2048]

        try:
            resp = await asyncio.to_thread(requests.post, url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            self.update_model(model)
            raise NotImplementedError()
        except Exception as ex:
            logger.debug("Ошибка построения эмбедингов: %s", ex)
