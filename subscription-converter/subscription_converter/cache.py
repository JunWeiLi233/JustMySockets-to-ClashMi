"""Thread-safe TTL cache.

The cache key is derived from the subscription URL via HMAC-SHA256 using a
per-process random key. This means:

* Raw URLs are never used as cache keys or written to logs.
* We never log the URL — only a short, un-reversible digest.

Cached values can contain parsed proxy credentials. They are therefore purged
at expiry and cleared during application shutdown; they are never persisted.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

logger = logging.getLogger("subscription_converter.cache")

T = TypeVar("T")

__all__ = ["TTLCache"]


@dataclass
class _Entry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    """Simple bounded LRU + TTL cache. All public methods are concurrency-safe."""

    def __init__(self, ttl_seconds: int, max_entries: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: OrderedDict[str, _Entry[T]] = OrderedDict()
        self._lock = threading.Lock()
        # Random per-process secret. Never persisted, never logged.
        self._secret = os.urandom(32)

    def key_for(self, url: str) -> str:
        """Return a stable, opaque HMAC digest for a URL (never logged in full)."""
        return hmac.new(self._secret, url.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def mask(key: str) -> str:
        """Short, log-safe prefix of a digest (cannot be reversed)."""
        return key[:8]

    def get(self, url: str) -> T | None:
        key = self.key_for(url)
        now = time.monotonic()
        with self._lock:
            self._purge_expired_locked(now)
            entry = self._store.get(key)
            if entry is None:
                return None
            self._store.move_to_end(key)
            logger.debug("cache hit key=%s", self.mask(key))
            return entry.value

    def set(self, url: str, value: T) -> None:
        key = self.key_for(url)
        now = time.monotonic()
        with self._lock:
            self._purge_expired_locked(now)
            while len(self._store) >= self._max:
                self._store.popitem(last=False)
            self._store[key] = _Entry(value=value, expires_at=now + self._ttl)
            self._store.move_to_end(key)

    def invalidate(self, url: str) -> None:
        key = self.key_for(url)
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        now = time.monotonic()
        with self._lock:
            self._purge_expired_locked(now)
            return len(self._store)

    def purge_expired(self) -> int:
        """Remove all expired values and return the number purged."""
        now = time.monotonic()
        with self._lock:
            return self._purge_expired_locked(now)

    def _purge_expired_locked(self, now: float) -> int:
        expired = [key for key, entry in self._store.items() if entry.expires_at <= now]
        for key in expired:
            self._store.pop(key, None)
        if expired:
            logger.debug("purged expired cache entries count=%d", len(expired))
        return len(expired)

    def get_or_set(self, url: str, factory: Callable[[], T]) -> T:
        """Return the cached value or compute via ``factory`` and cache it.

        The factory runs outside the lock, so concurrent callers may compute the
        same value twice (acceptable for subscription conversion; keeps the lock
        duration minimal).
        """
        cached = self.get(url)
        if cached is not None:
            return cached
        value = factory()
        self.set(url, value)
        return value
