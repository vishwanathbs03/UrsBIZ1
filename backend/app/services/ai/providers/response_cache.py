"""ResponseCache — Sprint H8.9 In-memory response cache for zero-latency AI responses."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


class ResponseCache:
    """In-memory LRU response cache storing grounded responses for identical prompt/context hashes."""

    def __init__(self, max_entries: int = 100) -> None:
        self._cache: dict[str, Any] = {}
        self._max_entries = max_entries

    def _hash_key(self, user_prompt: str, business_id: int) -> str:
        raw = f"{business_id}:{user_prompt.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, user_prompt: str, business_id: int) -> Any | None:
        """Retrieve cached response if present."""
        key = self._hash_key(user_prompt, business_id)
        return self._cache.get(key)

    def put(self, user_prompt: str, business_id: int, response: Any) -> None:
        """Cache response object."""
        if len(self._cache) >= self._max_entries:
            # Evict oldest key
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        key = self._hash_key(user_prompt, business_id)
        self._cache[key] = response

    def clear(self) -> None:
        self._cache.clear()
