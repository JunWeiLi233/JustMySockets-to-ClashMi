"""Small in-process sliding-window limiter with pseudonymous bucket keys."""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass

__all__ = ["RateDecision", "SlidingWindowRateLimiter"]


@dataclass(frozen=True)
class RateDecision:
    """Result of one atomic multi-identity rate-limit check."""

    allowed: bool
    retry_after: int = 0


class SlidingWindowRateLimiter:
    """Bound requests without retaining raw device tokens or network addresses.

    The key is random per process. Buckets disappear after their window, so this
    is deliberately a short-lived abuse control rather than an identity store.
    Durable creation quotas are enforced atomically by :class:`LinkStore`.
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._key = secrets.token_bytes(32)
        self._buckets: dict[bytes, deque[float]] = {}
        self._expires_at: dict[bytes, float] = {}
        self._checks = 0
        self._lock = threading.Lock()

    def check(
        self,
        scope: str,
        identities: Iterable[str],
        *,
        limit: int,
        window_seconds: int,
    ) -> RateDecision:
        """Check all identities atomically and charge each only on success."""
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("rate limit and window must be positive")
        keys = tuple(
            {
                hmac.digest(
                    self._key,
                    f"{scope}\x00{identity}".encode(),
                    "sha256",
                )
                for identity in identities
            }
        )
        if not keys:
            raise ValueError("at least one rate-limit identity is required")

        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            self._checks += 1
            if self._checks % 256 == 0:
                expired = [key for key, expiry in self._expires_at.items() if expiry <= now]
                for key in expired:
                    self._buckets.pop(key, None)
                    self._expires_at.pop(key, None)

            retry_after = 0
            for key in keys:
                bucket = self._buckets.get(key)
                if bucket is None:
                    continue
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if not bucket:
                    self._buckets.pop(key, None)
                    self._expires_at.pop(key, None)
                    continue
                if len(bucket) >= limit:
                    retry_after = max(
                        retry_after,
                        max(1, int(bucket[0] + window_seconds - now) + 1),
                    )
            if retry_after:
                return RateDecision(allowed=False, retry_after=retry_after)
            for key in keys:
                self._buckets.setdefault(key, deque()).append(now)
                self._expires_at[key] = now + window_seconds
        return RateDecision(allowed=True)
