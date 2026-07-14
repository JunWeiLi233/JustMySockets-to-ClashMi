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
from subscription_converter.network_guard import SSRFError, UrlValidator
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
        url_validator: UrlValidator | None = None,
        max_response_bytes: int = 8 * 1024 * 1024,
        max_redirects: int = 3,
    ) -> None:
        self._registry = registry
        self._user_agent = user_agent
        self._timeout = timeout
        self._url_validator = url_validator
        self._max_response_bytes = max_response_bytes
        self._max_redirects = max_redirects

    # ------------------------------------------------------------------ #
    # Fetching
    # ------------------------------------------------------------------ #
    async def fetch_async(self, url: str) -> httpx.Response:
        if not url.startswith(("http://", "https://")):
            raise SubscriptionFetchError("url must use http or https")
        # Pre-flight SSRF check (also re-run on each redirect by the hook below).
        if self._url_validator is not None:
            try:
                self._url_validator.validate(url)
            except (SSRFError, ValueError) as exc:
                raise SubscriptionFetchError(f"url rejected: {exc.__class__.__name__}") from exc
        try:
            async with httpx.AsyncClient(  # noqa: SIM117 -- client must exist before .stream()
                timeout=self._timeout,
                follow_redirects=True,
                max_redirects=self._max_redirects,
                event_hooks={"request": [self._request_hook]},
                # Some subscription providers return a mismatched compressed
                # response through their CDN. Identity encoding also ensures
                # our byte cap applies to exactly what the provider sends.
                headers={"User-Agent": self._user_agent, "Accept-Encoding": "identity"},
            ) as client:
                # Stream so we can enforce a hard cap on response size (A2).
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    body = await self._read_capped(resp)
                    # Re-materialize the response with the bounded body so callers
                    # keep the same .text / .headers interface.
                    return httpx.Response(
                        status_code=resp.status_code,
                        headers=resp.headers,
                        content=body,
                        request=resp.request,
                    )
        except httpx.HTTPStatusError as exc:
            raise SubscriptionFetchError(
                f"upstream returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.TooManyRedirects as exc:
            raise SubscriptionFetchError("upstream redirected too many times") from exc
        except httpx.DecodingError as exc:
            raise SubscriptionFetchError("upstream sent an invalid encoded response") from exc
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise SubscriptionFetchError(
                f"failed to fetch subscription: {exc.__class__.__name__}"
            ) from exc

    async def _request_hook(self, request: httpx.Request) -> None:
        """Re-validate every request (including redirect targets) against the SSRF guard."""
        if self._url_validator is None:
            return
        try:
            self._url_validator.validate(str(request.url))
        except (SSRFError, ValueError) as exc:
            raise SubscriptionFetchError(f"url rejected: {exc.__class__.__name__}") from exc

    async def _read_capped(self, resp: httpx.Response) -> bytes:
        """Read the streaming body up to ``max_response_bytes`` (A2: OOM defence)."""
        chunks: list[bytes] = []
        total = 0
        async for chunk in resp.aiter_bytes():
            total += len(chunk)
            if total > self._max_response_bytes:
                raise SubscriptionFetchError(
                    f"upstream body exceeds {self._max_response_bytes} bytes"
                )
            chunks.append(chunk)
        return b"".join(chunks)

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
        # Strip CR/LF from header values to prevent response-header injection
        # if these are later echoed back to the client (A5).
        filtered = {
            k: "".join(c for c in v if c not in "\r\n")
            for k, v in upstream_headers.items()
            if k.lower() in safe
        }
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        _ = time.monotonic()  # reserved for future age-based cache logic
        return Subscription(
            nodes=nodes,
            fetched_at_iso=now_iso,
            upstream_headers=filtered,
        )
