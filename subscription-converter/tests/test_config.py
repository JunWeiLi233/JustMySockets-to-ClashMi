"""Tests for the Settings configuration."""

from __future__ import annotations

import os

import pytest
from subscription_converter.config import Settings

__all__ = ()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear subscription-converter env vars so tests are deterministic."""
    for key in list(os.environ):
        if key.isupper() and any(
            key.startswith(p)
            for p in (
                "HOST",
                "PORT",
                "WORKERS",
                "CACHE_",
                "FETCH_",
                "TEST_",
                "DNS_",
                "LOG_LEVEL",
                "ENABLE_DOCS",
                "ALLOWED_HOSTS",
                "PERSISTENT_LINKS_",
                "LINK_",
                "MAX_ACTIVE_LINKS",
                "MAX_LINKS_PER_SOURCE",
                "PUBLIC_BASE_URL",
                "ALLOW_LEGACY_URL_ENDPOINTS",
            )
        ):
            monkeypatch.delenv(key, raising=False)


def test_defaults() -> None:
    s = Settings()
    assert s.host == "0.0.0.0"
    assert s.port == 8000
    assert s.cache_ttl_seconds == 300
    assert s.fetch_timeout_seconds == 15.0
    assert s.fetch_user_agent == "clash.meta/1.18"
    assert s.test_url == "https://www.gstatic.com/generate_204"
    assert "https://dns.alidns.com/dns-query" in s.dns_nameserver
    assert s.dns_ipv6 is False
    assert s.enable_docs is False
    assert s.allowed_hosts == ()
    assert s.persistent_links_enabled is False
    assert s.link_database_path == "/var/data/subscriptions.sqlite3"
    assert s.link_secret_key == ""
    assert s.max_active_links == 100
    assert s.max_links_per_source == 3
    assert s.public_base_url == ""
    assert s.allow_legacy_url_endpoints is True


def test_reads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("CACHE_TTL_SECONDS", "120")
    monkeypatch.setenv("DNS_IPV6", "true")
    monkeypatch.setenv("ENABLE_DOCS", "yes")
    monkeypatch.setenv("ALLOWED_HOSTS", "a.com,b.com")
    monkeypatch.setenv("DNS_NAMESERVER", "https://x.example/dns-query,https://y.example/dns-query")
    monkeypatch.setenv("PERSISTENT_LINKS_ENABLED", "true")
    monkeypatch.setenv("LINK_DATABASE_PATH", "/tmp/links.sqlite3")
    monkeypatch.setenv("LINK_SECRET_KEY", "private-value")
    monkeypatch.setenv("MAX_ACTIVE_LINKS", "42")
    monkeypatch.setenv("MAX_LINKS_PER_SOURCE", "2")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://service.example/")
    monkeypatch.setenv("ALLOW_LEGACY_URL_ENDPOINTS", "false")
    s = Settings()
    assert s.port == 9000
    assert s.cache_ttl_seconds == 120
    assert s.dns_ipv6 is True
    assert s.enable_docs is True
    assert s.allowed_hosts == ("a.com", "b.com")
    assert s.dns_nameserver == ("https://x.example/dns-query", "https://y.example/dns-query")
    assert s.persistent_links_enabled is True
    assert s.link_database_path == "/tmp/links.sqlite3"
    assert s.link_secret_key == "private-value"
    assert s.max_active_links == 42
    assert s.max_links_per_source == 2
    assert s.public_base_url == "https://service.example"
    assert s.allow_legacy_url_endpoints is False
    assert "private-value" not in repr(s)


def test_invalid_int_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "not-a-number")
    assert Settings().port == 8000


def test_is_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    import dataclasses

    s = Settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.port = 9999  # type: ignore[misc]


def test_with_overrides_returns_new_instance() -> None:
    s = Settings()
    s2 = s.with_overrides(port=4242)
    assert s.port == 8000  # original unchanged
    assert s2.port == 4242
    assert s2 is not s


def test_with_overrides_preserves_other_fields() -> None:
    s = Settings()
    s2 = s.with_overrides(port=4242)
    assert s2.host == s.host
    assert s2.cache_ttl_seconds == s.cache_ttl_seconds
    assert s2.dns_nameserver == s.dns_nameserver
