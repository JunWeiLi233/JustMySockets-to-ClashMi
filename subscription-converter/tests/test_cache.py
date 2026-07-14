"""Tests for the TTL cache."""

from __future__ import annotations

import time

import pytest
from subscription_converter.cache import TTLCache

__all__ = ()


def test_set_and_get_round_trip() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=10)
    assert cache.get("https://sub.example.com/x") is None
    cache.set("https://sub.example.com/x", "value")
    assert cache.get("https://sub.example.com/x") == "value"


def test_get_returns_none_after_expiry() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=1, max_entries=10)
    cache.set("u", "v")
    assert cache.get("u") == "v"
    time.sleep(1.1)
    assert cache.get("u") is None


def test_size_purges_all_expired_values() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=1, max_entries=10)
    cache.set("u1", "credential-1")
    cache.set("u2", "credential-2")
    time.sleep(1.1)
    assert cache.size() == 0
    assert cache.purge_expired() == 0


def test_invalidate() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=10)
    cache.set("u", "v")
    cache.invalidate("u")
    assert cache.get("u") is None


def test_clear() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=10)
    cache.set("u1", "v1")
    cache.set("u2", "v2")
    cache.clear()
    assert cache.size() == 0


def test_lru_eviction_when_capacity_reached() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=2)
    cache.set("u1", "v1")
    cache.set("u2", "v2")
    cache.set("u3", "v3")  # evicts u1 (oldest)
    assert cache.size() == 2
    assert cache.get("u1") is None
    assert cache.get("u3") == "v3"


def test_get_or_set_invokes_factory_once_on_hit() -> None:
    cache: TTLCache[int] = TTLCache(ttl_seconds=60, max_entries=10)
    calls = {"n": 0}

    def factory() -> int:
        calls["n"] += 1
        return 42

    assert cache.get_or_set("u", factory) == 42
    assert cache.get_or_set("u", factory) == 42
    assert calls["n"] == 1


def test_key_for_is_opaque_and_does_not_contain_url() -> None:
    """The derived key must not reveal the URL."""
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=10)
    url = "https://sub.example.com/x?token=secret"
    key = cache.key_for(url)
    assert "secret" not in key
    assert "sub.example.com" not in key
    assert len(key) == 64  # sha256 hex


def test_mask_is_short_prefix() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=10)
    key = cache.key_for("u")
    assert TTLCache.mask(key) == key[:8]


def test_invalid_constructor_args() -> None:
    with pytest.raises(ValueError):
        TTLCache(ttl_seconds=0, max_entries=1)
    with pytest.raises(ValueError):
        TTLCache(ttl_seconds=1, max_entries=0)


def test_distinct_urls_get_distinct_keys() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=10)
    assert cache.key_for("u1") != cache.key_for("u2")
