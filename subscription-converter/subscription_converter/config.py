"""Application configuration.

All settings are read from environment variables with sensible production
defaults, exposed as an immutable :class:`Settings` dataclass. There is no
global mutable state: a single instance is constructed and injected where
needed (dependency injection).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace

__all__ = ["Settings"]


def _as_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _as_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _as_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _as_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return tuple(part.strip() for part in raw.split(",") if part.strip())


_DEFAULT_DNS_NAMESERVER: tuple[str, ...] = (
    "https://dns.alidns.com/dns-query",
    "https://doh.pub/dns-query",
)
_DEFAULT_DNS_FALLBACK: tuple[str, ...] = (
    "https://1.1.1.1/dns-query",
    "https://dns.google/dns-query",
)
_DEFAULT_DNS_BOOTSTRAP: tuple[str, ...] = ("223.5.5.5", "119.29.29.29")


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration.

    Frozen so it can be safely shared across threads / async tasks without
    accidental mutation. Use :meth:`with_overrides` to derive a new instance.

    Note: the DNS resolvers below are PUBLIC recursive resolvers, never proxy
    servers. Proxy endpoints come exclusively from the upstream subscription.
    """

    # Server
    host: str = field(default_factory=lambda: os.environ.get("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _as_int("PORT", 8000))
    workers: int = field(default_factory=lambda: _as_int("WORKERS", 2))

    # Cache
    cache_ttl_seconds: int = field(default_factory=lambda: _as_int("CACHE_TTL_SECONDS", 300))
    cache_max_entries: int = field(default_factory=lambda: _as_int("CACHE_MAX_ENTRIES", 512))

    # Upstream fetch
    fetch_timeout_seconds: float = field(
        default_factory=lambda: _as_float("FETCH_TIMEOUT_SECONDS", 15.0)
    )
    fetch_user_agent: str = field(
        default_factory=lambda: os.environ.get("FETCH_USER_AGENT", "clash.meta/1.18")
    )

    # Proxy group / url-test behaviour
    test_url: str = field(
        default_factory=lambda: os.environ.get("TEST_URL", "https://www.gstatic.com/generate_204")
    )
    test_interval: int = field(default_factory=lambda: _as_int("TEST_INTERVAL", 300))

    # DNS resolvers (public resolvers, NOT proxy servers)
    dns_nameserver: tuple[str, ...] = field(
        default_factory=lambda: _as_csv("DNS_NAMESERVER", _DEFAULT_DNS_NAMESERVER)
    )
    dns_fallback: tuple[str, ...] = field(
        default_factory=lambda: _as_csv("DNS_FALLBACK", _DEFAULT_DNS_FALLBACK)
    )
    dns_bootstrap: tuple[str, ...] = field(
        default_factory=lambda: _as_csv("DNS_BOOTSTRAP", _DEFAULT_DNS_BOOTSTRAP)
    )
    dns_fake_ip_range: str = field(
        default_factory=lambda: os.environ.get("DNS_FAKE_IP_RANGE", "198.18.0.1/16")
    )
    dns_ipv6: bool = field(default_factory=lambda: _as_bool("DNS_IPV6", False))

    # Misc
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO").upper())
    allowed_hosts: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()
        )
    )

    def with_overrides(self, **kwargs: object) -> Settings:
        """Return a copy with the given fields overridden."""
        return replace(self, **kwargs)  # type: ignore[arg-type]
