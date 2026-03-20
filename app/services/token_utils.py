from __future__ import annotations

from typing import Optional, List
from app.models.assistant_models import MemoryMessage
import logging

logger = logging.getLogger(__name__)


def estimate_tokens(text: str, model: Optional[str] = None) -> int:
    """Эвристическая оценка токенов. Если доступен tiktoken, можно улучшить.
    По умолчанию ~4 символа = 1 токен.
    Если указан model, можно выбрать подходящую кодировку (упрощение).
    """
    if not text:
        return 0
    try:
        # try to use tiktoken if installed
        import tiktoken
        try:
            # choose encoding based on model hint if possible
            enc_name = 'cl100k_base'
            if model and isinstance(model, str) and model.startswith('gpt-2'):
                enc_name = 'gpt2'
            enc = tiktoken.get_encoding(enc_name)
            return max(1, len(enc.encode(text)))
        except Exception:
            # fallback heuristic
            return max(1, len(text) // 4)
    except Exception:
        return max(1, len(text) // 4)


def truncate_messages(messages: List[MemoryMessage], token_budget: int, model: Optional[str] = None) -> List[MemoryMessage]:
    """Усечь список сообщений до token_budget (приблизительно), удаляя старые сообщения сначала."""
    if not messages:
        return []
    retained: List[MemoryMessage] = []
    # iterate from newest to oldest adding until budget exceeded
    total = 0
    for m in reversed(messages):
        t = estimate_tokens(m.content or '', model=model)
        if total + t > token_budget:
            break
        retained.append(m)
        total += t
    # retained is reversed (newest first), return in chronological order
    return list(reversed(retained))


def summarize_context(messages: List[MemoryMessage], max_summary_tokens: int = 150) -> str:
    """Быстрая локальная суммаризация: собирает заголовки и первые N символов из сообщений.
    Это дешёвая эвристика, подходящая для уменьшения контекста без вызова внешних LLM.
    """
    if not messages:
        return ""
    parts = []
    for m in messages[-10:]:
        txt = (m.content or '').strip().replace('\n', ' ')
        if not txt:
            continue
        # take up to 120 chars per message
        parts.append(txt[:120])
        if sum(len(p) for p in parts) > (max_summary_tokens * 4):
            break
    summary = ' '.join(parts)
    # truncate summary to approximate token count
    if len(summary) > max_summary_tokens * 4:
        summary = summary[:max_summary_tokens * 4]
    return summary
