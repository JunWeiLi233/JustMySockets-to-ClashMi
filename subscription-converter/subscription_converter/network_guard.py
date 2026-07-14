"""SSRF guard for the upstream fetch path.

Blocks requests to private, loopback, link-local, and cloud-metadata addresses
before the subscription is downloaded. This protects the service from being
abused as a proxy into the internal network (e.g. AWS/GCP metadata at
169.254.169.254).

The resolver is injected so tests can substitute a no-op resolver (avoiding
real DNS); production uses :func:`default_resolver`, which calls
``socket.getaddrinfo``.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

logger = logging.getLogger("subscription_converter.network_guard")

__all__ = ["SSRFError", "UrlValidator", "default_resolver", "default_url_validator"]

# Cloud metadata endpoints and other sensitive hostnames. The link-local IP
# 169.254.169.254 is also caught by is_link_local, but listing the DNS names
# catches them before resolution.
_BLOCKED_HOSTNAMES: frozenset[str] = frozenset(
    {
        "localhost",  # resolves to 127.0.0.1 / ::1
        "metadata.google.internal",  # GCP metadata
        "metadata.aws.internal",
    }
)


class SSRFError(ValueError):
    """Raised when a URL points at a blocked address (SSRF attempt)."""


_IP = ipaddress.IPv4Address | ipaddress.IPv6Address


def _is_blocked_ip(ip: _IP) -> bool:
    """True if the IP is private/loopback/link-local/reserved/multicast/non-global."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or not ip.is_global
    )


def _hostname_to_ip(host: str) -> _IP | None:
    """Parse a hostname into an IP object, handling decimal/octal/hex IPv4 forms.

    Returns ``None`` for DNS names (resolved separately by the resolver).
    """
    cleaned = host.strip("[]")
    try:
        return ipaddress.ip_address(cleaned)
    except ValueError:
        pass
    # Decimal / octal / hex IPv4 forms (e.g. 2130706433 == 127.0.0.1)
    try:
        return ipaddress.IPv4Address(int(cleaned))
    except (ValueError, TypeError):
        pass
    return None


def default_resolver(host: str) -> list[str]:
    """Production DNS resolver: returns the raw address strings from getaddrinfo.

    Raises ``SSRFError`` on resolution failure so callers can't distinguish
    "blocked" from "unresolvable" — both are rejected.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise SSRFError("could not resolve host") from exc
    addrs: list[str] = []
    for info in infos:
        addr = info[4][0]
        if isinstance(addr, bytes):
            addr = addr.decode("ascii", "ignore")
        addrs.append(str(addr))
    return addrs


@dataclass(frozen=True)
class UrlValidator:
    """Validates URLs and (optionally) resolved IPs to enforce the SSRF deny-list."""

    allowed_hosts: frozenset[str] = frozenset()
    resolver: Callable[[str], list[str]] = field(default=default_resolver)

    def validate(self, url: str) -> None:
        """Raise :class:`SSRFError` or ``ValueError`` if the URL is unsafe to fetch."""
        if not url:
            raise ValueError("missing 'url' query parameter")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("url must use http or https")
        host = parsed.hostname
        if not host:
            raise ValueError("url has no hostname")
        host_lower = host.lower()

        if host_lower in _BLOCKED_HOSTNAMES:
            raise SSRFError("blocked host")

        # Optional allow-list (hostname-level).
        if self.allowed_hosts and host_lower not in self.allowed_hosts:
            raise ValueError(f"host '{host_lower}' is not allowed")

        # Direct IP literal — check immediately.
        direct_ip = _hostname_to_ip(host)
        if direct_ip is not None:
            if _is_blocked_ip(direct_ip):
                raise SSRFError("blocked address")
            return

        # DNS name — resolve and check every returned address.
        resolved = self.resolver(host_lower)
        for addr in resolved:
            try:
                ip = ipaddress.ip_address(addr)
            except ValueError:
                continue
            if _is_blocked_ip(ip):
                raise SSRFError("blocked address")


def default_url_validator(
    allowed_hosts: tuple[str, ...] = (),
    *,
    resolve: bool = True,
) -> UrlValidator:
    """Build a production validator.

    Set ``resolve=False`` for environments without DNS (e.g. tests) — IP literals
    are still checked, but DNS names are allowed through without resolution.
    """
    return UrlValidator(
        allowed_hosts=frozenset(h.lower() for h in allowed_hosts),
        resolver=default_resolver if resolve else (lambda _host: []),
    )
