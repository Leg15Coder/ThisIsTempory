from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from collections import deque
from typing import Optional

try:
    import redis
except Exception:
    redis = None


class RateLimiter:
    """Простейший локальный/Redis rate limiter с подсчетом RPD и RPM.

    Если Redis доступен (REDIS_URL), использует Redis для распределённых счетчиков и очередей.
    В противном случае использует локальную память (подходит для dev).
    """

    def __init__(self, redis_url: Optional[str] = None, rpm: int = 12, rpd: int = 450):
        self.rpm_limit = int(rpm)
        self.rpd_limit = int(rpd)
        self.lock = threading.Lock()
        self._date = datetime.now(timezone.utc).date()
        # counters: { model_name: { 'rpd': int, 'rpm': int, 'last_minute_ts': int } }
        self.counters: dict[str, dict] = {}
        # per-minute deque for RPM in local mode: { model_name: deque([timestamps]) }
        self.deques: dict[str, deque] = {}
        self.redis_client = None
        if redis and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
            except Exception:
                self.redis_client = None

        # concurrency tracking (local fallback)
        # { model_name: current_concurrent_count }
        self._concurrency_counters: dict[str, int] = {}
        # lock already present for thread-safety

    def _reset_if_new_day(self):
        today = datetime.now(timezone.utc).date()
        if today != self._date:
            with self.lock:
                self.counters = {}
                self.deques = {}
                self._date = today

    def would_exceed_rpd(self, model: str, increase: int = 1) -> bool:
        """Проверяет, превысит ли счётчик RPD при добавлении increase вызовов."""
        self._reset_if_new_day()
        if self.redis_client:
            key = f"ratelimiter:rpd:{model}:{self._date.isoformat()}"
            try:
                cur = int(self.redis_client.get(key) or 0)
                return (cur + increase) > int(self.rpd_limit * 0.9)
            except Exception:
                pass
        with self.lock:
            cur = self.counters.get(model, {}).get('rpd', 0)
            return (cur + increase) > int(self.rpd_limit * 0.9)

    def increment(self, model: str, amount: int = 1):
        self._reset_if_new_day()
        if self.redis_client:
            key = f"ratelimiter:rpd:{model}:{self._date.isoformat()}"
            try:
                self.redis_client.incrby(key, amount)
                # set expiry for key to 2 days
                self.redis_client.expire(key, 60 * 60 * 48)
                return
            except Exception:
                pass
        with self.lock:
            if model not in self.counters:
                self.counters[model] = {'rpd': 0}
            self.counters[model]['rpd'] = self.counters[model].get('rpd', 0) + int(amount)

    def get_rpd(self, model: str) -> int:
        self._reset_if_new_day()
        if self.redis_client:
            key = f"ratelimiter:rpd:{model}:{self._date.isoformat()}"
            try:
                return int(self.redis_client.get(key) or 0)
            except Exception:
                pass
        with self.lock:
            return int(self.counters.get(model, {}).get('rpd', 0))

    def reset_daily(self):
        with self.lock:
            self.counters = {}
            self.deques = {}
            self._date = datetime.now(timezone.utc).date()

    def enqueue_request(self, model: str, payload: str):
        """Добавляет запрос в очередь для модели. payload должен быть сериализуемой строкой (JSON)."""
        if self.redis_client:
            try:
                key = f"ratelimiter:queue:{model}"
                self.redis_client.rpush(key, payload)
                # keep queue reasonably bounded (optional)
                self.redis_client.ltrim(key, -1000, -1)
                return
            except Exception:
                pass
        # local deque
        with self.lock:
            dq = self.deques.setdefault(f"queue:{model}", deque())
            dq.append(payload)
            # bound to 1000
            while len(dq) > 1000:
                dq.popleft()

    def dequeue_request(self, model: str) -> Optional[str]:
        """Извлекает следующий запрос из очереди (FIFO). Возвращает payload или None."""
        if self.redis_client:
            try:
                key = f"ratelimiter:queue:{model}"
                val = self.redis_client.lpop(key)
                return val
            except Exception:
                pass
        with self.lock:
            dq = self.deques.get(f"queue:{model}")
            if dq and len(dq):
                return dq.popleft()
        return None

    # New concurrency helpers
    def acquire_concurrency(self, model: str, max_concurrent: int = 6, timeout: int = 10) -> bool:
        """Попытаться зарезервировать слот для одновременного вызова модели.
        Возвращает True если слот успешно захвачен, False если таймаут/переполнение.
        Локальная реализация использует блокировку и счетчик; при наличии Redis можно расширить на INCR с TTL.
        """
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                cur = self._concurrency_counters.get(model, 0)
                if cur < max_concurrent:
                    self._concurrency_counters[model] = cur + 1
                    return True
            time.sleep(0.05)
        return False

    def release_concurrency(self, model: str):
        """Освободить ранее захваченный слот для модели."""
        with self.lock:
            cur = self._concurrency_counters.get(model, 0)
            if cur <= 1:
                self._concurrency_counters.pop(model, None)
            else:
                self._concurrency_counters[model] = cur - 1


# singleton accessor
_limiter: Optional[RateLimiter] = None


def get_rate_limiter(redis_url: Optional[str] = None, rpm: int = 12, rpd: int = 450) -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(redis_url=redis_url, rpm=rpm, rpd=rpd)
    return _limiter
