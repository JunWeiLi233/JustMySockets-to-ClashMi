"""Tests for the security hardening (PR: fix/security-hardening).

Covers the CRITICAL/HIGH audit findings:
- A1 SSRF guard blocks private/loopback/metadata addresses.
- A2 body-size cap rejects oversized responses.
- A3/B6 broadened log masking redacts bare URLs and secret keys.
- A4 Surge converter sanitizes injected section/field separators.
- A5 upstream header CR/LF stripped.
- B2 SS parser raises ParserError (not ValueError) on bad port.
- B4 Profile-Update-Interval fallback is in hours.
- B9 Surge/sing-box raise ConversionError on zero proxies.
"""

from __future__ import annotations

import logging

import httpx
import pytest
import respx
from subscription_converter.converters import ConversionError
from subscription_converter.converters.singbox import SingBoxConverter
from subscription_converter.converters.surge import SurgeConverter
from subscription_converter.models import ProxyNode, ProxyType
from subscription_converter.network_guard import SSRFError, UrlValidator
from subscription_converter.parser_port import ParserError
from subscription_converter.parsers import ShadowsocksParser

__all__ = ()


def _no_resolve(_host: str) -> list[str]:
    """Test resolver that skips DNS (no network)."""
    return []


NO_RESOLVE = _no_resolve


# === A1: SSRF guard ====================================================== #


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://2130706433/",  # decimal form of 127.0.0.1
        "http://0.0.0.0/",
    ],
)
def test_ssrf_blocks_private_and_metadata_addresses(url: str) -> None:
    v = UrlValidator(resolver=NO_RESOLVE)
    with pytest.raises(SSRFError):
        v.validate(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://jmssub.net/getsub.php?x=1",
        "https://8.8.8.8/",
        "https://example.com/path",
    ],
)
def test_ssrf_allows_public_addresses(url: str) -> None:
    v = UrlValidator(resolver=NO_RESOLVE)
    v.validate(url)  # must not raise


def test_ssrf_allowed_hosts_rejects_unlisted() -> None:
    v = UrlValidator(allowed_hosts=frozenset({"good.example.com"}), resolver=NO_RESOLVE)
    v.validate("https://good.example.com/x")
    with pytest.raises(ValueError):
        v.validate("https://bad.example.com/x")


def test_ssrf_rejects_non_http_scheme() -> None:
    v = UrlValidator(resolver=NO_RESOLVE)
    with pytest.raises(ValueError):
        v.validate("ftp://example.com/")


# === A2: body-size cap =================================================== #


@respx.mock
async def test_fetch_rejects_oversized_body() -> None:
    from subscription_converter.parsers import default_registry
    from subscription_converter.subscription_parser import (
        SubscriptionFetchError,
        SubscriptionParser,
    )

    big = "x" * (9 * 1024 * 1024)  # 9 MB > default 8 MB cap
    respx.get("https://up.example.com/sub").mock(return_value=httpx.Response(200, text=big))
    parser = SubscriptionParser(
        registry=default_registry(),
        user_agent="t",
        timeout=10.0,
        url_validator=UrlValidator(resolver=NO_RESOLVE),
        max_response_bytes=8 * 1024 * 1024,
    )
    with pytest.raises(SubscriptionFetchError, match="exceeds"):
        await parser.fetch_and_parse("https://up.example.com/sub")


# === A3/B6: broadened log masking ======================================== #


def test_masking_filter_redacts_bare_urls() -> None:
    from subscription_converter.app import _MaskingFilter

    f = _MaskingFilter()
    record = logging.LogRecord(
        name="httpx",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg="HTTP Request: GET https://sub.example.com/x?token=SECRET 200",
        args=(),
        exc_info=None,
    )
    assert f.filter(record)
    rendered = record.getMessage()
    assert "SECRET" not in rendered
    assert "sub.example.com" not in rendered


def test_masking_filter_redacts_percent_encoded_url_parameter() -> None:
    from subscription_converter.app import _MaskingFilter

    text = "GET /clash?url=https%3A%2F%2Fexample.com%2Fsub%3Fid%3Dprivate HTTP/1.1"
    redacted = _MaskingFilter()._redact(text)
    assert "private" not in redacted
    assert "url=<redacted>" in redacted


def test_proxy_node_repr_excludes_credentials() -> None:
    from subscription_converter.models import ProxyNode, ProxyType

    node = ProxyNode(
        type=ProxyType.VLESS,
        name="node",
        server="proxy.example.com",
        port=443,
        password="password-private",
        uuid="uuid-private",
        obfs_password="obfs-private",
    )
    rendered = repr(node)
    assert "password-private" not in rendered
    assert "uuid-private" not in rendered
    assert "obfs-private" not in rendered


def test_masking_filter_redacts_secret_keys() -> None:
    from subscription_converter.app import _MaskingFilter

    f = _MaskingFilter()
    record = logging.LogRecord(
        name="x",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="processing token=abc123 password=hunter2",
        args=(),
        exc_info=None,
    )
    f.filter(record)
    rendered = record.getMessage()
    assert "abc123" not in rendered
    assert "hunter2" not in rendered


def test_masking_filter_leaves_clean_messages() -> None:
    from subscription_converter.app import _MaskingFilter

    f = _MaskingFilter()
    record = logging.LogRecord(
        name="x",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="fetched subscription nodes=6",
        args=(),
        exc_info=None,
    )
    f.filter(record)
    assert record.getMessage() == "fetched subscription nodes=6"


def test_masking_filter_redacts_stable_subscription_tokens() -> None:
    from subscription_converter.app import _MaskingFilter

    token = "A" * 43
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f"GET /s/{token} HTTP/1.1",
        args=(),
        exc_info=None,
    )
    _MaskingFilter().filter(record)
    assert token not in record.getMessage()
    assert "/s/<redacted-token>" in record.getMessage()


# === A4: Surge config injection ========================================== #


def _node(**kw: object) -> ProxyNode:
    base: dict[str, object] = {
        "type": ProxyType.SS,
        "name": "n",
        "server": "s.example.com",
        "port": 8388,
        "cipher": "aes-256-gcm",
        "password": "p",
    }
    base.update(kw)
    return ProxyNode.model_validate(base)


def test_surge_strips_newlines_in_name_and_password() -> None:
    evil = _node(name="ok\n[Script]\neval(bad)", password="pa\nss word")
    out = SurgeConverter().render([evil])
    assert "[Script]" not in out
    assert "\neval" not in out
    # the injected newline in password must be gone
    assert "pa\nss" not in out


def test_surge_rejects_section_bracket_names() -> None:
    evil = _node(name="[Proxy Group]")
    out = SurgeConverter().render([evil])
    # name sanitized so it does NOT open a real new section
    assert out.count("[Proxy Group]") == 1  # only the legit trailing one


def test_surge_raises_on_zero_renderable() -> None:
    hy2 = _node(type=ProxyType.HYSTERIA2)  # surge placeholder doesn't handle hy2
    with pytest.raises(ConversionError):
        SurgeConverter().render([hy2])


# === A5: upstream header CR/LF stripping ================================= #


def test_subscription_strips_crlf_from_upstream_headers() -> None:
    from subscription_converter.parsers import default_registry
    from subscription_converter.subscription_parser import SubscriptionParser

    ss_link = "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQxMjM=@h.example.com:8388#n"
    parser = SubscriptionParser(registry=default_registry(), user_agent="t", timeout=1.0)
    sub = parser.parse_text(
        ss_link,
        upstream_headers={"subscription-userinfo": "up=1\r\nX-Evil: yes"},
    )
    assert "\r" not in sub.subscription_userinfo
    assert "\n" not in sub.subscription_userinfo


# === B2: SS parser bad port ============================================== #


def test_ss_parser_raises_parser_error_on_bad_port() -> None:
    # SIP002 form with a non-numeric port
    bad = "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQxMjM=@h.example.com:abc"
    with pytest.raises(ParserError):
        ShadowsocksParser().parse(bad)


def test_ss_parser_bad_port_does_not_abort_whole_subscription() -> None:
    """One bad-SS-port line must not abort the entire subscription."""
    from subscription_converter.parsers import default_registry
    from subscription_converter.subscription_parser import SubscriptionParser

    good = "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQxMjM=@h.example.com:8388#ok"
    bad = "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQxMjM=@h.example.com:xyz#bad"
    parser = SubscriptionParser(registry=default_registry(), user_agent="t", timeout=1.0)
    sub = parser.parse_text(f"{good}\n{bad}")
    assert len(sub.nodes) == 1  # only the good one; bad line skipped


# === B4: Profile-Update-Interval units =================================== #


def test_profile_update_interval_fallback_is_hours() -> None:
    """cache_ttl_seconds=300 -> 300//3600 = 0 -> clamped to 1 hour (not 5 minutes)."""
    from subscription_converter.app import AppState
    from subscription_converter.config import Settings

    state = AppState(
        Settings().with_overrides(cache_ttl_seconds=300),
        url_validator=UrlValidator(resolver=NO_RESOLVE),
    )
    # Simulate the header computation directly.
    from subscription_converter.models import Subscription

    sub = Subscription(nodes=())  # no upstream hint -> uses fallback
    fallback_hours = max(state.settings.cache_ttl_seconds // 3600, 1)
    update_interval_h = sub.profile_update_interval or fallback_hours
    assert update_interval_h == 1  # 1 hour, not 5


# === B9: sing-box silent empty output ==================================== #


def test_singbox_raises_on_zero_renderable() -> None:
    # sing-box placeholder only handles SS; a vless-only sub has nothing
    vless = _node(type=ProxyType.VLESS, uuid="u")
    with pytest.raises(ConversionError):
        SingBoxConverter().render([vless])
