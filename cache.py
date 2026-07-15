"""
cache.py — Response cache with hit/miss counters (Renuka Task 4).

Keyed on (provider, prompt text, max_tokens, temperature), so the same
input never re-runs the model. hits/misses feed cache_hit_rate in
/metrics.
"""

import hashlib
from collections import OrderedDict
from threading import Lock
from typing import Optional


class ResponseCache:
    def __init__(self, max_size: int = 256):
        self.max_size = max_size
        self._store: "OrderedDict[str, str]" = OrderedDict()
        self._lock = Lock()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(provider: str, prompt: str, max_tokens: int, temperature: float) -> str:
        raw = f"{provider}|{max_tokens}|{temperature}|{prompt}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if key in self._store:
                self.hits += 1
                self._store.move_to_end(key)
                return self._store[key]
            self.misses += 1
            return None

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)  # evict oldest

    @property
    def hit_rate(self) -> float:
        with self._lock:
            total = self.hits + self.misses
            return round(self.hits / total, 4) if total else 0.0