"""FastAPI application exposing the subscription converter.

Endpoints
---------
* ``GET /``           -> health string ``Subscription Converter Running``
* ``GET /health``     -> JSON health + cache size
* ``GET /clash``      -> Mihomo / Clash Meta YAML (``application/yaml``)
* ``GET /surge``      -> Surge config (placeholder renderer, same pipeline)
* ``GET /sing-box``   -> sing-box JSON (placeholder renderer, same pipeline)

All conversion endpoints take ``?url=...`` and an optional
``&force_refresh=true`` to bypass the cache and re-download the upstream
immediately.

Security
--------
The subscription URL (and any credentials embedded in it) is never logged. A
process-wide logging filter redacts any ``url=...`` value, and the cache stores
only HMAC digests of URLs.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Final
from urllib.parse import urlparse

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import PlainTextResponse, Response

from subscription_converter.cache import TTLCache
from subscription_converter.config import Settings
from subscription_converter.converter_registry import get_converter
from subscription_converter.converters import BaseConverter, ConversionError
from subscription_converter.converters.mihomo import MihomoConverter
from subscription_converter.models import Subscription
from subscription_converter.parser_port import ParserRegistry
from subscription_converter.parsers import default_registry
from subscription_converter.subscription_parser import (
    SubscriptionFetchError,
    SubscriptionParseError,
    SubscriptionParser,
)
from subscription_converter.url_input import (
    InvalidSubscriptionURL,
    normalize_subscription_url,
)

__all__ = ["AppState", "app", "create_app"]

logger = logging.getLogger("subscription_converter.app")

# Router declared at import time so route handlers below can attach to it, and
# create_app() can include it. MUST precede create_app()'s body.
router = APIRouter()

# Upstream response headers we surface to clients (lowercased).
_USERINFO_HEADER: Final[str] = "subscription-userinfo"


# --------------------------------------------------------------------------- #
# Logging: redact any url=... value from every log record.
# --------------------------------------------------------------------------- #


class _MaskingFilter(logging.Filter):
    """Strip the value of any ``url=`` parameter from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        if "url=" in msg:
            record.msg = _redact_url(msg)
            record.args = ()
        return True


def _redact_url(text: str) -> str:
    out: list[str] = []
    i = 0
    needle = "url="
    while True:
        idx = text.find(needle, i)
        if idx < 0:
            out.append(text[i:])
            break
        out.append(text[i : idx + len(needle)])
        start_val = idx + len(needle)
        end_val = start_val
        while end_val < len(text) and not text[end_val].isspace():
            end_val += 1
        out.append("<redacted>")
        i = end_val
    return "".join(out)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    filt = _MaskingFilter()
    root = logging.getLogger()
    root.addFilter(filt)
    for name in ("uvicorn", "uvicorn.access", "fastapi", "subscription_converter"):
        logging.getLogger(name).addFilter(filt)


# --------------------------------------------------------------------------- #
# Application state (dependency-injection container; no module-level globals).
# --------------------------------------------------------------------------- #


class AppState:
    """Holds long-lived collaborators, created once at startup.

    The cache stores the **parsed upstream subscription** (nodes), not a
    rendered document. The YAML is regenerated dynamically on every request so
    it always reflects the current cached upstream and the current converter
    settings.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.registry: ParserRegistry = default_registry()
        self.parser = SubscriptionParser(
            registry=self.registry,
            user_agent=settings.fetch_user_agent,
            timeout=settings.fetch_timeout_seconds,
        )
        self.cache: TTLCache[Subscription] = TTLCache(
            ttl_seconds=settings.cache_ttl_seconds,
            max_entries=settings.cache_max_entries,
        )

    def make_converter(self, fmt: str) -> BaseConverter:
        if fmt in {"clash", "mihomo"}:
            return MihomoConverter(
                test_url=self.settings.test_url,
                test_interval=self.settings.test_interval,
                dns_nameserver=self.settings.dns_nameserver,
                dns_fallback=self.settings.dns_fallback,
                dns_bootstrap=self.settings.dns_bootstrap,
                dns_fake_ip_range=self.settings.dns_fake_ip_range,
                dns_ipv6=self.settings.dns_ipv6,
            )
        return get_converter(
            fmt,
            test_url=self.settings.test_url,
            test_interval=self.settings.test_interval,
        )


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #


def _validate_url(url: str, settings: Settings) -> None:
    if not url:
        raise ValueError("missing 'url' query parameter")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("url must use http or https")
    if not parsed.hostname:
        raise ValueError("url has no hostname")
    if settings.allowed_hosts and parsed.hostname.lower() not in {
        h.lower() for h in settings.allowed_hosts
    }:
        raise ValueError(f"host '{parsed.hostname}' is not allowed")


class _ConvertHTTPError(Exception):
    """Internal sentinel translated to an HTTP 400 in handlers."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


# --------------------------------------------------------------------------- #
# Core: cached fetch + dynamic render
# --------------------------------------------------------------------------- #


async def _fetch_subscription(state: AppState, url: str, *, force_refresh: bool) -> Subscription:
    """Return the current upstream Subscription, using the TTL cache.

    - Without ``force_refresh`` the upstream is re-downloaded at most once per
      ``cache_ttl_seconds``.
    - With ``force_refresh`` the cache is bypassed and the upstream is
      re-downloaded immediately, then the cache entry is replaced.
    """
    if not force_refresh:
        cached = state.cache.get(url)
        if cached is not None:
            logger.debug(
                "subscription cache hit key=%s fetched_at=%s nodes=%d",
                state.cache.mask(state.cache.key_for(url)),
                cached.fetched_at_iso,
                len(cached.nodes),
            )
            return cached

    try:
        subscription = await state.parser.fetch_and_parse(url)
    except (SubscriptionFetchError, SubscriptionParseError) as exc:
        raise _ConvertHTTPError(str(exc)) from exc

    logger.info(
        "fetched subscription key=%s fetched_at=%s nodes=%d",
        state.cache.mask(state.cache.key_for(url)),
        subscription.fetched_at_iso,
        len(subscription.nodes),
    )
    state.cache.set(url, subscription)
    return subscription


def _render_format(state: AppState, fmt: str, subscription: Subscription) -> tuple[str, str]:
    """Render the cached subscription into ``fmt``. Pure; runs every request."""
    converter = state.make_converter(fmt)
    try:
        rendered = converter.render(subscription.nodes)
    except ConversionError as exc:
        raise _ConvertHTTPError(str(exc)) from exc
    return rendered, converter.media_type


# --------------------------------------------------------------------------- #
# Factory + lifespan
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _default_settings() -> Settings:
    return Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Prefer settings attached by create_app(); fall back to env-derived defaults.
    settings: Settings = getattr(app.state, "settings", None) or _default_settings()
    configure_logging(settings.log_level)
    state = AppState(settings)
    app.state.app_state = state
    logger.info(
        "startup complete (workers hint=%d, cache_ttl=%ds)",
        settings.workers,
        settings.cache_ttl_seconds,
    )
    try:
        yield
    finally:
        app.state.app_state = None
        logger.info("shutdown complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or _default_settings()
    app_obj = FastAPI(
        title="subscription-converter",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    # Attach settings so the lifespan can use the caller-provided configuration
    # (dependency injection) rather than always reading env-derived defaults.
    app_obj.state.settings = s
    app_obj.include_router(router)
    _default_settings.cache_clear()
    os.environ.setdefault("LOG_LEVEL", s.log_level)
    return app_obj


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


def _state(request: Request) -> AppState:
    state: AppState | None = getattr(request.app.state, "app_state", None)
    if state is None:  # pragma: no cover - lifespan always sets it
        raise RuntimeError("application state not initialised")
    return state


@router.get("/")
async def root() -> PlainTextResponse:
    return PlainTextResponse("Subscription Converter Running")


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    state = _state(request)
    return {"status": "ok", "cache_size": state.cache.size()}


async def _convert_endpoint(
    request: Request, fmt: str, *, allow_force_refresh: bool = True
) -> Response:
    """Shared handler for all conversion endpoints.

    The user's subscription URL is read from the **raw query string** (not the
    FastAPI ``url`` query param) so that unencoded ``?``/``&`` characters in a
    pasted URL are preserved. The raw value is then run through
    :func:`normalize_subscription_url`, which forgives stray backslashes,
    leading ``%20`` spaces, and accidental double-encoding. This means users
    can paste any of these and still get a working conversion:

    - ``?url=https://x.net/s?service=1&id=2``  (unencoded, raw paste)
    - ``?url=https%3A%2F%2Fx.net%2Fs%3Fservice%3D1%26id%3D2``  (pre-encoded)
    - ``?url=https://x.net/s\\?service\\=1\\&id=2``  (shell-escaped)
    """
    state = _state(request)
    raw_url, force_refresh = _extract_url_and_refresh(request, allow_force_refresh)

    try:
        url = normalize_subscription_url(raw_url)
        _validate_url(url, state.settings)
    except (ValueError, InvalidSubscriptionURL) as exc:
        return PlainTextResponse(f"invalid request: {exc}", status_code=400)

    try:
        subscription = await asyncio.wait_for(
            _fetch_subscription(state, url, force_refresh=force_refresh),
            timeout=state.settings.fetch_timeout_seconds + 5,
        )
        rendered, media_type = _render_format(state, fmt, subscription)
    except _ConvertHTTPError as exc:
        return PlainTextResponse(f"conversion failed: {exc.message}", status_code=400)
    except TimeoutError:
        return PlainTextResponse("conversion failed: upstream fetch timed out", status_code=504)
    except Exception as exc:  # never crash the process
        logger.exception("unexpected error: %s", exc.__class__.__name__)
        return PlainTextResponse(
            f"conversion failed: unexpected {exc.__class__.__name__}", status_code=400
        )

    update_interval_h = subscription.profile_update_interval or max(
        state.settings.cache_ttl_seconds // 60, 1
    )
    headers = {
        "Cache-Control": f"public, max-age={state.settings.cache_ttl_seconds}",
        "X-Subscription-Fetched-At": subscription.fetched_at_iso,
        "Subscription-Userinfo": subscription.subscription_userinfo,
        "Profile-Update-Interval": str(update_interval_h if update_interval_h >= 1 else 1),
    }
    return Response(content=rendered, media_type=media_type, headers=headers)


def _extract_url_and_refresh(request: Request, allow_force_refresh: bool) -> tuple[str, bool]:
    """Pull the raw ``url=`` value and optional ``force_refresh`` from the query.

    Reads the raw query string so a pasted URL containing unencoded ``&`` (which
    FastAPI would otherwise split into separate params) is reconstructed in
    full. The ``force_refresh`` flag is detected conservatively.
    """
    raw_qs = request.url.query or ""
    # Split on '&' only where it separates a key=val pair that is NOT part of
    # the user's URL. We treat the first 'url=' as the start; everything after
    # it up to the trailing '&force_refresh=...' belongs to the subscription URL.
    # Strategy: find 'url=' (case-insensitive), capture the rest, then peel off
    # a trailing '&force_refresh=true|1|yes' if present.
    idx = _find_url_key(raw_qs)
    if idx is None:
        return "", False
    value = raw_qs[idx + len("url=") :]
    force = False
    m = _TRAILING_FORCE_REFRESH.search(value)
    if m and allow_force_refresh:
        force = _as_bool(m.group(1))
        value = value[: m.start()].rstrip("&")
    # The captured value is still percent-encoded at the transport layer
    # (urlencoded query string). We decode known-safe chars here so the
    # downstream normalizer sees a readable value; further decoding logic lives
    # in normalize_subscription_url.
    from urllib.parse import unquote

    return unquote(value), force


def _find_url_key(qs: str) -> int | None:
    """Return the index of the ``url=`` key in the raw query string.

    Matches ``url=`` at the start, or after an ``&``. Case-insensitive.
    """
    lowered = qs.lower()
    if lowered.startswith("url="):
        return 0
    pos = lowered.find("&url=")
    if pos >= 0:
        return pos + 1
    return None


def _as_bool(v: str) -> bool:
    return v.strip().lower() in {"1", "true", "yes", "on"}


_TRAILING_FORCE_REFRESH = re.compile(r"(?:^|&)force_refresh=([^&]+)$", re.IGNORECASE)


@router.get("/clash")
async def clash(request: Request) -> Response:
    """Mihomo / Clash Meta compatible YAML endpoint."""
    return await _convert_endpoint(request, "clash")


@router.get("/surge")
async def surge(request: Request) -> Response:
    """Surge config (placeholder renderer; same parser)."""
    return await _convert_endpoint(request, "surge")


@router.get("/sing-box")
async def sing_box(request: Request) -> Response:
    """sing-box JSON config (placeholder renderer; same parser)."""
    return await _convert_endpoint(request, "sing-box")


# --------------------------------------------------------------------------- #
# Module-level application instance (after all routes are defined).
# --------------------------------------------------------------------------- #

app = create_app()
