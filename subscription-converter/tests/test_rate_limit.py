"""Tests for the short-lived pseudonymous request limiter."""

from __future__ import annotations

from subscription_converter.rate_limit import SlidingWindowRateLimiter

__all__ = ()


def test_multi_identity_limit_is_atomic_and_expires() -> None:
    now = [100.0]
    limiter = SlidingWindowRateLimiter(clock=lambda: now[0])

    first = limiter.check("create", ("device-a", "network-a"), limit=2, window_seconds=60)
    second = limiter.check("create", ("device-b", "network-a"), limit=2, window_seconds=60)
    denied = limiter.check("create", ("device-c", "network-a"), limit=2, window_seconds=60)
    assert first.allowed
    assert second.allowed
    assert not denied.allowed
    assert denied.retry_after > 0

    # The denied request was not charged to device-c, and the old network
    # window disappears cleanly.
    now[0] = 161.0
    assert limiter.check("create", ("device-c", "network-a"), limit=2, window_seconds=60).allowed
