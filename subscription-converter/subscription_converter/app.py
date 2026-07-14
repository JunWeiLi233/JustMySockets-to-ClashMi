"""FastAPI application exposing the subscription converter.

Endpoints
---------
* ``GET /``           -> private browser UI for building client URLs
* ``GET /health``     -> JSON health + cache size
* ``POST /api/check`` -> private same-origin subscription validation
* ``POST /api/links`` -> encrypted durable link creation
* ``POST /api/links/close`` -> permanent closure by private management key
* ``GET /admin``      -> one-browser, pseudonymous operations dashboard
* ``GET /s/{token}``  -> config through an opaque durable access token
* ``GET /clash``      -> Mihomo / Clash Meta YAML (``application/yaml``)
* ``GET /surge``      -> Surge config (placeholder renderer, same pipeline)
* ``GET /sing-box``   -> sing-box JSON (placeholder renderer, same pipeline)

All conversion endpoints take ``?url=...`` and an optional
``&force_refresh=true`` to bypass the cache and re-download the upstream
immediately.

Security
--------
The subscription URL (and any credentials embedded in it) is never logged. A
process-wide logging filter redacts URL and opaque-token shapes. Durable source
URLs use authenticated encryption; cache and database lookups use HMAC digests.
"""

from __future__ import annotations

import asyncio
import hmac
import ipaddress
import logging
import os
import re
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Final, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from subscription_converter.admin_frontend import (
    render_admin_dashboard,
    render_admin_enrollment,
)
from subscription_converter.cache import TTLCache
from subscription_converter.config import Settings
from subscription_converter.converter_registry import get_converter
from subscription_converter.converters import BaseConverter, ConversionError
from subscription_converter.converters.mihomo import MihomoConverter
from subscription_converter.frontend import render_frontend
from subscription_converter.link_store import (
    CapacityReached,
    DuplicateSourceLimitReached,
    LinkStore,
    LinkStoreConfigurationError,
    LinkStoreCorruptionError,
    NetworkLimitReached,
    UserLimitReached,
)
from subscription_converter.models import Subscription
from subscription_converter.network_guard import SSRFError, UrlValidator, default_url_validator
from subscription_converter.parser_port import ParserRegistry
from subscription_converter.parsers import default_registry
from subscription_converter.rate_limit import SlidingWindowRateLimiter
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
_NO_STORE: Final[str] = "private, no-store, max-age=0"
_CLIENT_COOKIE: Final[str] = "jms_client_device"
_ADMIN_COOKIE: Final[str] = "jms_admin_device"
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]{43}$")
_PERMISSIONS_POLICY: Final[str] = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=(), payment=(), usb=()"
)


# --------------------------------------------------------------------------- #
# Logging: redact any url=... value from every log record.
# --------------------------------------------------------------------------- #


class _MaskingFilter(logging.Filter):
    """Redact subscription URLs and credentials from every log record.

    Catches four leak shapes:
    1. ``url=<value>`` tokens (our own structured logs).
    2. Bare ``https?://...`` URLs anywhere (httpx DEBUG request logs, exception
       messages that embed the upstream URL).
    3. ``<secret-key>=<value>`` tokens for credential-ish keys
       (token / password / secret / key / auth / uuid / sid / id).
    4. Opaque access tokens in ``/s/<token>`` request paths.
    """

    _URL_PARAM_RE = re.compile(r"(?i)(\burl=)[^\s'\"]+")
    _URL_RE = re.compile(r"https?://[^\s'\"]+", re.IGNORECASE)
    _SECRET_RE = re.compile(r"(?i)(token|password|passwd|secret|key|auth|uuid|sid|id)=\S+")
    _STABLE_PATH_RE = re.compile(r"(?i)(/s/)[A-Za-z0-9_-]{32,128}")

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        redacted = self._redact(msg)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True

    def _redact(self, text: str) -> str:
        text = self._URL_PARAM_RE.sub(r"\1<redacted>", text)
        text = self._URL_RE.sub("<redacted-url>", text)
        text = self._SECRET_RE.sub(lambda m: m.group(1) + "=<redacted>", text)
        text = self._STABLE_PATH_RE.sub(r"\1<redacted-token>", text)
        return text


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    filt = _MaskingFilter()
    root = logging.getLogger()
    root.addFilter(filt)
    # Cover the libraries that emit request/URL details. These propagate to the
    # root logger by default; attaching explicitly is belt-and-braces against a
    # library setting ``propagate = False``.
    for name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "httpx",
        "httpcore",
        "anyio",
        "h11",
        "subscription_converter",
    ):
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

    def __init__(
        self,
        settings: Settings,
        *,
        url_validator: UrlValidator | None = None,
    ) -> None:
        self.settings = settings
        self._validate_identity_settings(settings)
        self.registry: ParserRegistry = default_registry()
        # Production resolves DNS to block SSRF; tests inject a no-resolve validator.
        self.url_validator = url_validator or default_url_validator(settings.allowed_hosts)
        self.parser = SubscriptionParser(
            registry=self.registry,
            user_agent=settings.fetch_user_agent,
            timeout=settings.fetch_timeout_seconds,
            url_validator=self.url_validator,
        )
        self.cache: TTLCache[Subscription] = TTLCache(
            ttl_seconds=settings.cache_ttl_seconds,
            max_entries=settings.cache_max_entries,
        )
        self.rate_limiter = SlidingWindowRateLimiter()
        self.link_store: LinkStore | None = None
        if settings.persistent_links_enabled:
            self._validate_public_base_url(settings.public_base_url)
            self._validate_admin_bootstrap_secret(settings.admin_bootstrap_secret)
            self.link_store = LinkStore(
                settings.link_database_path,
                settings.link_secret_key,
                max_active_links=settings.max_active_links,
                max_links_per_source=settings.max_links_per_source,
                max_links_per_user=settings.max_links_per_user,
                max_links_per_network=settings.max_links_per_network,
            )

    @staticmethod
    def _validate_public_base_url(value: str) -> None:
        parsed = urlsplit(value)
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        if not parsed.netloc or (parsed.scheme != "https" and not local_http):
            raise LinkStoreConfigurationError(
                "PUBLIC_BASE_URL must be an absolute HTTPS URL (or local HTTP URL)"
            )
        if (
            parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise LinkStoreConfigurationError(
                "PUBLIC_BASE_URL must be an origin without credentials, path, or query"
            )

    @staticmethod
    def _validate_admin_bootstrap_secret(value: str) -> None:
        if value and _TOKEN_RE.fullmatch(value) is None:
            raise LinkStoreConfigurationError(
                "ADMIN_BOOTSTRAP_SECRET must be an unpadded URL-safe base64 32-byte token"
            )

    @staticmethod
    def _validate_identity_settings(settings: Settings) -> None:
        positive_values = {
            "CLIENT_COOKIE_MAX_AGE_SECONDS": settings.client_cookie_max_age_seconds,
            "ADMIN_COOKIE_MAX_AGE_SECONDS": settings.admin_cookie_max_age_seconds,
            "CHECK_RATE_LIMIT": settings.check_rate_limit,
            "CHECK_RATE_WINDOW_SECONDS": settings.check_rate_window_seconds,
            "CREATE_RATE_LIMIT": settings.create_rate_limit,
            "CREATE_RATE_WINDOW_SECONDS": settings.create_rate_window_seconds,
            "CLOSE_RATE_LIMIT": settings.close_rate_limit,
            "CLOSE_RATE_WINDOW_SECONDS": settings.close_rate_window_seconds,
            "ADMIN_ENROLL_RATE_LIMIT": settings.admin_enroll_rate_limit,
            "ADMIN_ENROLL_RATE_WINDOW_SECONDS": settings.admin_enroll_rate_window_seconds,
        }
        invalid = next((name for name, value in positive_values.items() if value <= 0), None)
        if invalid is not None:
            raise LinkStoreConfigurationError(f"{invalid} must be positive")
        header = settings.trusted_client_ip_header
        if header and re.fullmatch(r"[A-Za-z0-9-]+", header) is None:
            raise LinkStoreConfigurationError("TRUSTED_CLIENT_IP_HEADER is invalid")

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


@dataclass(frozen=True)
class _ClientIdentity:
    owner_token: str
    network_identity: str
    is_new: bool


def _network_identity(request: Request, settings: Settings) -> str:
    """Return a canonical address for ephemeral HMAC-based network controls."""
    candidates: list[str] = []
    header = settings.trusted_client_ip_header
    if header:
        # The operator must opt in only when a trusted edge supplies this
        # header. Standard forwarding chains put the original client first.
        candidates.extend(request.headers.get(header, "").split(","))
    if request.client is not None:
        candidates.append(request.client.host)
    for candidate in candidates:
        try:
            return ipaddress.ip_address(candidate.strip()).compressed
        except ValueError:
            continue
    return "unavailable"


def _client_identity(
    request: Request, state: AppState, *, create: bool = True
) -> _ClientIdentity | None:
    token = request.cookies.get(_CLIENT_COOKIE, "")
    if _TOKEN_RE.fullmatch(token) is not None:
        return _ClientIdentity(
            owner_token=token,
            network_identity=_network_identity(request, state.settings),
            is_new=False,
        )
    if not create:
        return None
    return _ClientIdentity(
        owner_token=secrets.token_urlsafe(32),
        network_identity=_network_identity(request, state.settings),
        is_new=True,
    )


def _cookie_secure(request: Request, state: AppState) -> bool:
    return request.url.scheme == "https" or state.settings.public_base_url.startswith("https://")


def _set_client_cookie(
    response: Response,
    request: Request,
    state: AppState,
    identity: _ClientIdentity,
) -> None:
    if not identity.is_new:
        return
    response.set_cookie(
        _CLIENT_COOKIE,
        identity.owner_token,
        max_age=state.settings.client_cookie_max_age_seconds,
        secure=_cookie_secure(request, state),
        httponly=True,
        samesite="strict",
        path="/",
    )


def _rate_limit(
    state: AppState,
    identity: _ClientIdentity,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
) -> int:
    decision = state.rate_limiter.check(
        scope,
        (
            f"device:{identity.owner_token}",
            f"network:{identity.network_identity}",
        ),
        limit=limit,
        window_seconds=window_seconds,
    )
    return 0 if decision.allowed else decision.retry_after


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #


def _validate_url(url: str, state: AppState) -> None:
    """Validate the URL, enforcing the SSRF deny-list.

    Raises ``SSRFError`` for blocked addresses (private/loopback/metadata),
    and ``ValueError`` for malformed input. Both become HTTP 400/422 in the
    handler, but SSRF is logged at WARNING for monitoring.
    """
    try:
        state.url_validator.validate(url)
    except SSRFError:
        logger.warning("SSRF blocked (digest=%s)", state.cache.mask(state.cache.key_for(url)))
        raise


class _ConvertHTTPError(Exception):
    """Internal sentinel translated to an HTTP 400 in handlers."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class _CheckRequest(BaseModel):
    """Small, strict body accepted by the same-origin connection checker."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str = Field(min_length=1, max_length=4096)
    format: Literal["clash", "sing-box", "surge"] = "clash"
    force_refresh: bool = False


class _CreateLinkRequest(BaseModel):
    """Strict body for creating one durable subscription link."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str = Field(min_length=1, max_length=4096)
    format: Literal["clash", "sing-box", "surge"] = "clash"


class _CloseLinkRequest(BaseModel):
    """Management key submitted in a body so it never enters URL logs/history."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    manage_key: str = Field(min_length=1, max_length=128)


class _AdminEnrollRequest(BaseModel):
    """Bootstrap secret submitted once in a body, never in a URL."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    bootstrap_secret: str = Field(min_length=1, max_length=128)


class _AdminCloseRequest(BaseModel):
    """Non-bearer database reference accepted by the enrolled admin only."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    link_ref: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


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
    # Optional injected URL validator (tests pass a no-resolve one).
    url_validator: UrlValidator | None = getattr(app.state, "url_validator", None)
    state = AppState(settings, url_validator=url_validator)
    app.state.app_state = state
    purge_task = asyncio.create_task(_purge_expired_cache(state))
    logger.info(
        "startup complete (workers hint=%d, cache_ttl=%ds)",
        settings.workers,
        settings.cache_ttl_seconds,
    )
    try:
        yield
    finally:
        purge_task.cancel()
        with suppress(asyncio.CancelledError):
            await purge_task
        state.cache.clear()
        app.state.app_state = None
        logger.info("shutdown complete")


async def _purge_expired_cache(state: AppState) -> None:
    """Bound how long parsed proxy credentials remain in process memory."""
    interval = max(1, min(state.settings.cache_ttl_seconds, 60))
    while True:
        await asyncio.sleep(interval)
        state.cache.purge_expired()


def create_app(
    settings: Settings | None = None,
    *,
    url_validator: UrlValidator | None = None,
) -> FastAPI:
    s = settings or _default_settings()
    app_obj = FastAPI(
        title="subscription-converter",
        version="0.1.0",
        docs_url="/docs" if s.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if s.enable_docs else None,
        lifespan=lifespan,
    )

    @app_obj.middleware("http")
    async def security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Apply safe browser defaults without changing conversion semantics."""
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = _PERMISSIONS_POLICY
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        return response

    # Attach settings + optional validator so the lifespan can use them.
    app_obj.state.url_validator = url_validator
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


def _html_csp(nonce: str) -> str:
    return (
        "default-src 'none'; "
        f"style-src 'nonce-{nonce}'; "
        f"script-src 'nonce-{nonce}'; "
        "connect-src 'self'; img-src 'self' data:; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'"
    )


@router.get("/")
async def root(request: Request) -> HTMLResponse:
    state = _state(request)
    identity = _client_identity(request, state)
    assert identity is not None
    nonce = secrets.token_urlsafe(24)
    response = HTMLResponse(
        render_frontend(nonce=nonce),
        headers={
            "Cache-Control": _NO_STORE,
            "Content-Security-Policy": _html_csp(nonce),
            "Pragma": "no-cache",
        },
    )
    _set_client_cookie(response, request, state, identity)
    return response


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    state = _state(request)
    payload: dict[str, object] = {
        "status": "ok",
        "cache_size": state.cache.size(),
        "persistent_links": "disabled",
    }
    if state.link_store is not None:
        capacity = await asyncio.to_thread(state.link_store.capacity)
        payload.update(
            {
                "persistent_links": "ready",
                "active_links": capacity.active,
                "link_capacity": capacity.limit,
            }
        )
    return payload


def _check_error(message: str, *, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        {"status": "error", "message": message},
        status_code=status_code,
        headers={"Cache-Control": _NO_STORE, "Pragma": "no-cache"},
    )


def _api_error(
    code: str,
    message: str,
    *,
    status_code: int,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response_headers = {"Cache-Control": _NO_STORE, "Pragma": "no-cache"}
    if headers:
        response_headers.update(headers)
    return JSONResponse(
        {"status": "error", "code": code, "message": message},
        status_code=status_code,
        headers=response_headers,
    )


def _is_cross_site_browser(request: Request) -> bool:
    return request.headers.get("sec-fetch-site", "").lower() == "cross-site"


@router.post("/api/check")
async def check_subscription(request: Request, payload: _CheckRequest) -> JSONResponse:
    """Validate and render a subscription without placing its URL in request logs."""
    if _is_cross_site_browser(request):
        return _check_error("cross-site checks are not allowed", status_code=403)

    state = _state(request)
    identity = _client_identity(request, state)
    assert identity is not None
    retry_after = _rate_limit(
        state,
        identity,
        scope="check",
        limit=state.settings.check_rate_limit,
        window_seconds=state.settings.check_rate_window_seconds,
    )
    if retry_after:
        response = _check_error("too many checks; try again later", status_code=429)
        response.headers["Retry-After"] = str(retry_after)
        _set_client_cookie(response, request, state, identity)
        return response
    try:
        url = normalize_subscription_url(payload.url)
        if not url.lower().startswith("https://"):
            return _check_error("an HTTPS subscription URL is required")
        _validate_url(url, state)
    except SSRFError:
        return _check_error("url rejected: blocked address", status_code=422)
    except (ValueError, InvalidSubscriptionURL) as exc:
        return _check_error(f"invalid request: {exc}")

    try:
        subscription = await asyncio.wait_for(
            _fetch_subscription(state, url, force_refresh=payload.force_refresh),
            timeout=state.settings.fetch_timeout_seconds + 5,
        )
        _render_format(state, payload.format, subscription)
    except _ConvertHTTPError as exc:
        return _check_error(f"conversion failed: {exc.message}")
    except TimeoutError:
        return _check_error("conversion failed: upstream fetch timed out", status_code=504)
    except Exception as exc:
        logger.warning("unexpected check error: %s", exc.__class__.__name__)
        return _check_error(f"conversion failed: unexpected {exc.__class__.__name__}")

    response = JSONResponse(
        {
            "status": "ok",
            "nodes": len(subscription.nodes),
            "format": payload.format,
            "fetched_at": subscription.fetched_at_iso,
        },
        headers={"Cache-Control": _NO_STORE, "Pragma": "no-cache"},
    )
    _set_client_cookie(response, request, state, identity)
    return response


@router.get("/api/capacity")
async def link_capacity(request: Request) -> JSONResponse:
    """Public, non-sensitive availability used by the creation interface."""
    store = _state(request).link_store
    if store is None:
        return JSONResponse(
            {
                "status": "ok",
                "enabled": False,
                "accepting": False,
                "active": 0,
                "limit": 0,
                "remaining": 0,
            },
            headers={"Cache-Control": _NO_STORE, "Pragma": "no-cache"},
        )
    capacity = await asyncio.to_thread(store.capacity)
    return JSONResponse(
        {
            "status": "ok",
            "enabled": True,
            "accepting": capacity.accepting,
            "active": capacity.active,
            "limit": capacity.limit,
            "remaining": capacity.remaining,
        },
        headers={"Cache-Control": _NO_STORE, "Pragma": "no-cache"},
    )


@router.post("/api/links", status_code=201)
async def create_persistent_link(request: Request, payload: _CreateLinkRequest) -> JSONResponse:
    """Verify an upstream subscription, then create an encrypted durable link."""
    if _is_cross_site_browser(request):
        return _api_error(
            "cross_site",
            "cross-site link creation is not allowed",
            status_code=403,
        )

    state = _state(request)
    identity = _client_identity(request, state)
    assert identity is not None
    retry_after = _rate_limit(
        state,
        identity,
        scope="create",
        limit=state.settings.create_rate_limit,
        window_seconds=state.settings.create_rate_window_seconds,
    )
    if retry_after:
        response = _api_error(
            "rate_limited",
            "too many link creation attempts; try again later",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
        _set_client_cookie(response, request, state, identity)
        return response
    store = state.link_store
    if store is None:
        return _api_error(
            "not_enabled",
            "permanent subscription links are not enabled on this server",
            status_code=503,
        )

    capacity = await asyncio.to_thread(store.capacity)
    if not capacity.accepting:
        return _api_error(
            "capacity_reached",
            "new link creation is temporarily closed because all slots are in use",
            status_code=503,
            headers={"Retry-After": "3600"},
        )

    try:
        url = normalize_subscription_url(payload.url)
        if not url.lower().startswith("https://"):
            return _api_error(
                "https_required",
                "an HTTPS subscription URL is required",
                status_code=400,
            )
        _validate_url(url, state)
    except SSRFError:
        return _api_error("blocked_url", "url rejected: blocked address", status_code=422)
    except (ValueError, InvalidSubscriptionURL) as exc:
        return _api_error("invalid_url", f"invalid request: {exc}", status_code=400)

    try:
        subscription = await asyncio.wait_for(
            _fetch_subscription(state, url, force_refresh=True),
            timeout=state.settings.fetch_timeout_seconds + 5,
        )
        _render_format(state, payload.format, subscription)
    except _ConvertHTTPError as exc:
        return _api_error(
            "conversion_failed",
            f"conversion failed: {exc.message}",
            status_code=400,
        )
    except TimeoutError:
        return _api_error(
            "upstream_timeout",
            "conversion failed: upstream fetch timed out",
            status_code=504,
        )
    except Exception as exc:
        logger.warning("unexpected durable-link check error: %s", exc.__class__.__name__)
        return _api_error(
            "conversion_failed",
            f"conversion failed: unexpected {exc.__class__.__name__}",
            status_code=400,
        )

    try:
        created = await asyncio.to_thread(
            store.create,
            url,
            payload.format,
            owner_token=identity.owner_token,
            network_identity=identity.network_identity,
        )
    except CapacityReached:
        return _api_error(
            "capacity_reached",
            "new link creation is temporarily closed because all slots are in use",
            status_code=503,
            headers={"Retry-After": "3600"},
        )
    except DuplicateSourceLimitReached:
        return _api_error(
            "source_limit_reached",
            "this subscription already has the maximum number of permanent links",
            status_code=409,
        )
    except UserLimitReached:
        return _api_error(
            "user_limit_reached",
            "this browser device has the maximum number of active links",
            status_code=409,
        )
    except NetworkLimitReached:
        return _api_error(
            "network_limit_reached",
            "this network has the maximum number of active links",
            status_code=429,
            headers={"Retry-After": "3600"},
        )
    except Exception as exc:
        logger.error("durable link creation failed: %s", exc.__class__.__name__)
        return _api_error(
            "storage_unavailable",
            "permanent link storage is temporarily unavailable",
            status_code=503,
        )

    updated_capacity = await asyncio.to_thread(store.capacity)
    base_url = state.settings.public_base_url
    response = JSONResponse(
        {
            "status": "ok",
            "subscription_url": f"{base_url}/s/{created.access_token}",
            "manage_key": created.manage_key,
            "format": payload.format,
            "nodes": len(subscription.nodes),
            "created_at": created.created_at,
            "expires_at": None,
            "remaining": updated_capacity.remaining,
        },
        status_code=201,
        headers={"Cache-Control": _NO_STORE, "Pragma": "no-cache"},
    )
    _set_client_cookie(response, request, state, identity)
    return response


@router.post("/api/links/close")
async def close_persistent_link(request: Request, payload: _CloseLinkRequest) -> JSONResponse:
    """Permanently delete a link; the management key is never put in a URL."""
    if _is_cross_site_browser(request):
        return _api_error(
            "cross_site",
            "cross-site link closure is not allowed",
            status_code=403,
        )

    state = _state(request)
    identity = _client_identity(request, state)
    assert identity is not None
    retry_after = _rate_limit(
        state,
        identity,
        scope="close",
        limit=state.settings.close_rate_limit,
        window_seconds=state.settings.close_rate_window_seconds,
    )
    if retry_after:
        response = _api_error(
            "rate_limited",
            "too many link closure attempts; try again later",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
        _set_client_cookie(response, request, state, identity)
        return response
    store = state.link_store
    if store is None:
        return _api_error(
            "not_enabled",
            "permanent subscription links are not enabled on this server",
            status_code=503,
        )
    try:
        closed = await asyncio.to_thread(store.close, payload.manage_key)
    except Exception as exc:
        logger.error("durable link close failed: %s", exc.__class__.__name__)
        return _api_error(
            "storage_unavailable",
            "permanent link storage is temporarily unavailable",
            status_code=503,
        )
    if closed is None:
        return _api_error(
            "not_found",
            "management key not found; the link may already be closed",
            status_code=404,
        )
    if closed.source_url is not None:
        state.cache.invalidate(closed.source_url)
    response = JSONResponse(
        {"status": "closed", "message": "subscription link permanently closed"},
        headers={"Cache-Control": _NO_STORE, "Pragma": "no-cache"},
    )
    _set_client_cookie(response, request, state, identity)
    return response


def _admin_not_found() -> PlainTextResponse:
    """Conceal whether an admin route or enrollment exists."""
    return PlainTextResponse("not found", status_code=404)


async def _admin_credentials(
    request: Request,
) -> tuple[AppState, LinkStore, _ClientIdentity, str] | None:
    state = _state(request)
    store = state.link_store
    identity = _client_identity(request, state, create=False)
    device_token = request.cookies.get(_ADMIN_COOKIE, "")
    if store is None or identity is None or _TOKEN_RE.fullmatch(device_token) is None:
        return None
    if not await asyncio.to_thread(
        store.is_admin_device,
        device_token,
        identity.owner_token,
    ):
        return None
    return state, store, identity, device_token


@router.get("/admin/enroll")
async def admin_enrollment_page(request: Request) -> Response:
    """Expose a one-time form only before any admin browser is enrolled."""
    state = _state(request)
    store = state.link_store
    if (
        store is None
        or not state.settings.admin_bootstrap_secret
        or await asyncio.to_thread(store.admin_enrolled)
    ):
        return _admin_not_found()
    identity = _client_identity(request, state)
    assert identity is not None
    nonce = secrets.token_urlsafe(24)
    response = HTMLResponse(
        render_admin_enrollment(nonce=nonce),
        headers={
            "Cache-Control": _NO_STORE,
            "Content-Security-Policy": _html_csp(nonce),
            "Pragma": "no-cache",
        },
    )
    _set_client_cookie(response, request, state, identity)
    return response


@router.post("/api/admin/enroll", status_code=201)
async def enroll_admin_device(
    request: Request,
    payload: _AdminEnrollRequest,
) -> Response:
    """Bind the first valid enrollment to this browser profile."""
    if _is_cross_site_browser(request):
        return _admin_not_found()
    state = _state(request)
    store = state.link_store
    expected = state.settings.admin_bootstrap_secret
    if store is None or not expected or await asyncio.to_thread(store.admin_enrolled):
        return _admin_not_found()

    identity = _client_identity(request, state)
    assert identity is not None
    retry_after = _rate_limit(
        state,
        identity,
        scope="admin-enroll",
        limit=state.settings.admin_enroll_rate_limit,
        window_seconds=state.settings.admin_enroll_rate_window_seconds,
    )
    if retry_after:
        return PlainTextResponse(
            "too many requests",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    if not hmac.compare_digest(payload.bootstrap_secret, expected):
        return _admin_not_found()

    device_token = secrets.token_urlsafe(32)
    enrolled = await asyncio.to_thread(
        store.enroll_admin_device,
        device_token,
        identity.owner_token,
    )
    if not enrolled:
        return _admin_not_found()

    response = JSONResponse(
        {"status": "enrolled"},
        status_code=201,
        headers={"Cache-Control": _NO_STORE, "Pragma": "no-cache"},
    )
    _set_client_cookie(response, request, state, identity)
    response.set_cookie(
        _ADMIN_COOKIE,
        device_token,
        max_age=state.settings.admin_cookie_max_age_seconds,
        secure=_cookie_secure(request, state),
        httponly=True,
        samesite="strict",
        path="/",
    )
    return response


@router.get("/admin")
async def admin_dashboard(request: Request) -> Response:
    credentials = await _admin_credentials(request)
    if credentials is None:
        return _admin_not_found()
    _, store, _, device_token = credentials
    nonce = secrets.token_urlsafe(24)
    csrf_token = await asyncio.to_thread(store.admin_csrf_token, device_token)
    return HTMLResponse(
        render_admin_dashboard(nonce=nonce, csrf_token=csrf_token),
        headers={
            "Cache-Control": _NO_STORE,
            "Content-Security-Policy": _html_csp(nonce),
            "Pragma": "no-cache",
        },
    )


@router.get("/api/admin/overview")
async def admin_overview(request: Request) -> Response:
    credentials = await _admin_credentials(request)
    if credentials is None:
        return _admin_not_found()
    _, store, _, _ = credentials
    overview = await asyncio.to_thread(store.admin_overview)
    return JSONResponse(
        asdict(overview),
        headers={"Cache-Control": _NO_STORE, "Pragma": "no-cache"},
    )


@router.post("/api/admin/links/close")
async def admin_close_link(request: Request, payload: _AdminCloseRequest) -> Response:
    if _is_cross_site_browser(request):
        return _admin_not_found()
    credentials = await _admin_credentials(request)
    if credentials is None:
        return _admin_not_found()
    state, store, _, device_token = credentials
    csrf_token = request.headers.get("x-admin-csrf", "")
    if not await asyncio.to_thread(store.verify_admin_csrf, device_token, csrf_token):
        return PlainTextResponse("invalid request", status_code=403)
    closed = await asyncio.to_thread(store.admin_close, payload.link_ref)
    if closed is None:
        return _admin_not_found()
    if closed.source_url is not None:
        state.cache.invalidate(closed.source_url)
    return JSONResponse(
        {"status": "closed"},
        headers={"Cache-Control": _NO_STORE, "Pragma": "no-cache"},
    )


@router.get("/s/{access_token}")
async def persistent_subscription(request: Request, access_token: str) -> Response:
    """Resolve one opaque token and dynamically return its current config."""
    state = _state(request)
    store = state.link_store
    if store is None:
        return PlainTextResponse("subscription link not found", status_code=404)
    try:
        stored = await asyncio.to_thread(store.get, access_token)
    except LinkStoreCorruptionError:
        logger.error("stored subscription failed authenticated decryption")
        return PlainTextResponse("subscription link is temporarily unavailable", status_code=503)
    except Exception as exc:
        logger.error("durable link read failed: %s", exc.__class__.__name__)
        return PlainTextResponse("subscription link is temporarily unavailable", status_code=503)
    if stored is None:
        return PlainTextResponse("subscription link not found", status_code=404)

    try:
        _validate_url(stored.source_url, state)
    except (SSRFError, ValueError):
        return PlainTextResponse("stored subscription is no longer permitted", status_code=422)
    return await _convert_validated_url(
        state,
        stored.source_url,
        stored.format,
        force_refresh=False,
    )


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
    if not state.settings.allow_legacy_url_endpoints:
        return PlainTextResponse(
            "legacy URL subscriptions are disabled; create a private /s/ link on the home page",
            status_code=410,
        )
    raw_url, force_refresh = _extract_url_and_refresh(request, allow_force_refresh)

    try:
        url = normalize_subscription_url(raw_url)
        _validate_url(url, state)
    except SSRFError:
        # Deliberately generic message — never echo the blocked host back.
        return PlainTextResponse("url rejected: blocked address", status_code=422)
    except (ValueError, InvalidSubscriptionURL) as exc:
        return PlainTextResponse(f"invalid request: {exc}", status_code=400)

    return await _convert_validated_url(
        state,
        url,
        fmt,
        force_refresh=force_refresh,
    )


async def _convert_validated_url(
    state: AppState,
    url: str,
    fmt: str,
    *,
    force_refresh: bool,
) -> Response:
    """Fetch, render, and return a URL that has already passed SSRF validation."""
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
        # NOTE: do NOT use logger.exception here — the traceback can embed the
        # upstream URL (with credentials) inside httpx/anyio exception messages.
        logger.warning("unexpected error: %s", exc.__class__.__name__)
        return PlainTextResponse(
            f"conversion failed: unexpected {exc.__class__.__name__}", status_code=400
        )

    # Profile-Update-Interval is in HOURS per the Clash/Mihomo convention
    # (and Subscription.profile_update_interval). The fallback must also be in
    # hours: cache_ttl_seconds // 3600, clamped to >= 1 so clients poll at least
    # hourly. (B4: previously divided by 60 — minutes — causing 60x under-refresh.)
    fallback_hours = max(state.settings.cache_ttl_seconds // 3600, 1)
    update_interval_h = subscription.profile_update_interval or fallback_hours
    headers = {
        # Proxy configs contain credentials. Never allow a shared cache, CDN,
        # browser history cache, or intermediary to retain the rendered body.
        "Cache-Control": _NO_STORE,
        "Pragma": "no-cache",
        "X-Subscription-Fetched-At": subscription.fetched_at_iso,
        "Subscription-Userinfo": subscription.subscription_userinfo,
        "Profile-Update-Interval": str(max(update_interval_h, 1)),
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
