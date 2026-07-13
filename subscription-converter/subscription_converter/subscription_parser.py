"""Subscription orchestrator: fetch, detect format, decode, parse.

This module ties together HTTP fetching and the :class:`ParserRegistry`. It is
deliberately separated from the per-protocol parsers and from any output
format, so the same orchestrator feeds every converter.

Security
--------
- The subscription URL is never logged; callers receive only summary counts.
- Upstream response headers are filtered to a non-sensitive allow-list before
  being stored on the :class:`~subscription_converter.models.Subscription`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx

from subscription_converter.models import ProxyNode, Subscription
from subscription_converter.parser_port import ParserError, ParserRegistry
from subscription_converter.parsers._helpers import b64decode_loose, looks_like_base64

__all__ = ["SubscriptionFetchError", "SubscriptionParseError", "SubscriptionParser"]

logger = logging.getLogger("subscription_converter.parser")

# Non-sensitive upstream headers we are willing to retain on a Subscription.
# Auth/cookie headers are deliberately excluded.
_SAFE_UPSTREAM_HEADERS: frozenset[str] = frozenset(
    {
        "subscription-userinfo",
        "profile-update-interval",
        "profile-web-page-url",
        "content-disposition",
    }
)


class SubscriptionFetchError(RuntimeError):
    """Raised when the upstream subscription cannot be downloaded."""


class SubscriptionParseError(ValueError):
    """Raised when a subscription body yields no valid nodes."""


class SubscriptionParser:
    """Fetches and parses a subscription into a :class:`Subscription`.

    Stateless aside from injected HTTP settings, so it is safe to reuse across
    requests. The registry is injected (dependency injection) so tests can
    supply a fake registry.
    """

    def __init__(
        self,
        *,
        registry: ParserRegistry,
        user_agent: str,
        timeout: float,
    ) -> None:
        self._registry = registry
        self._user_agent = user_agent
        self._timeout = timeout

    # ------------------------------------------------------------------ #
    # Fetching
    # ------------------------------------------------------------------ #
    async def fetch_async(self, url: str) -> httpx.Response:
        if not url.startswith(("http://", "https://")):
            raise SubscriptionFetchError("url must use http or https")
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": self._user_agent},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp
        except httpx.HTTPStatusError as exc:
            raise SubscriptionFetchError(
                f"upstream returned HTTP {exc.response.status_code}"
            ) from exc
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise SubscriptionFetchError(
                f"failed to fetch subscription: {exc.__class__.__name__}"
            ) from exc

    # ------------------------------------------------------------------ #
    # Parsing
    # ------------------------------------------------------------------ #
    def parse_text(
        self,
        text: str,
        *,
        upstream_headers: Mapping[str, str] | None = None,
    ) -> Subscription:
        if not text or not text.strip():
            raise SubscriptionParseError("subscription body is empty")
        lines = self._normalise(text)
        if not lines:
            raise SubscriptionParseError("no recognisable links in subscription body")
        nodes: list[ProxyNode] = []
        for line in lines:
            node = self._parse_line(line)
            if node is not None:
                nodes.append(node)
        if not nodes:
            raise SubscriptionParseError("subscription produced 0 valid proxies")
        return self._build_subscription(tuple(nodes), upstream_headers or {})

    async def fetch_and_parse(self, url: str) -> Subscription:
        resp = await self.fetch_async(url)
        headers = {k.lower(): v for k, v in resp.headers.multi_items()}
        return self.parse_text(resp.text, upstream_headers=headers)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _normalise(self, text: str) -> list[str]:
        """Return clean URI lines from an arbitrary subscription body."""
        stripped = text.strip()
        # 1) Direct list of links.
        direct = [ln.strip() for ln in stripped.splitlines() if ln.strip() and "://" in ln]
        if direct:
            return direct
        # 2) Base64-encoded blob.
        if looks_like_base64(stripped):
            try:
                decoded = b64decode_loose(stripped).decode("utf-8", errors="strict")
            except (ValueError, UnicodeDecodeError):
                decoded = ""
            if decoded:
                return [ln.strip() for ln in decoded.splitlines() if ln.strip() and "://" in ln]
        # 3) Single bare link.
        if "://" in stripped:
            return [stripped]
        return []

    def _parse_line(self, line: str) -> ProxyNode | None:
        scheme = self._scheme_of(line)
        if scheme is None:
            return None
        # alias: hy2 -> hysteria2
        if scheme == "hy2":
            scheme = "hysteria2"
        parser = self._registry.get(scheme)
        if parser is None:
            logger.debug("no parser for scheme=%s", scheme)
            return None
        try:
            return parser.parse(line)
        except ParserError as exc:
            logger.debug("parse failed scheme=%s: %s", scheme, exc)
            return None

    @staticmethod
    def _scheme_of(uri: str) -> str | None:
        idx = uri.find("://")
        if idx <= 0:
            return None
        return uri[:idx].lower()

    @staticmethod
    def _build_subscription(
        nodes: tuple[ProxyNode, ...],
        upstream_headers: Mapping[str, str],
    ) -> Subscription:
        safe = _SAFE_UPSTREAM_HEADERS
        filtered = {k: v for k, v in upstream_headers.items() if k.lower() in safe}
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        _ = time.monotonic()  # reserved for future age-based cache logic
        return Subscription(
            nodes=nodes,
            fetched_at_iso=now_iso,
            upstream_headers=filtered,
        )
