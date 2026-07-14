"""Tests for the subscription orchestrator (fetch + decode + parse).

Uses ``respx`` to mock httpx so no real network is involved.
"""

from __future__ import annotations

import base64

import httpx
import pytest
import respx
from subscription_converter.models import ProxyType
from subscription_converter.parsers import default_registry
from subscription_converter.subscription_parser import (
    SubscriptionFetchError,
    SubscriptionParseError,
    SubscriptionParser,
)

__all__ = ()

SUB_URL = "https://sub.example.com/getsub.php?token=secret"

# A mixed body of links (fake creds).
SS_LINK = (
    "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQxMjM=@ss.example.com:8388"
    "/?plugin=obfs-local%3Bobfs%3Dtls%3Bobfs-host%3Dbing.com#ss-obfs-tls"
)
VMESS_LINK = (
    "vmess://"
    + base64.b64encode(
        b'{"v":"2","ps":"vmess","add":"vm.example.com","port":"443",'
        b'"id":"b831381d-6324-4d53-ad4f-8cda48b30811","aid":"0","net":"ws",'
        b'"path":"/ray","tls":"tls","sni":"cdn.example.com"}'
    ).decode()
)
TROJAN_LINK = "trojan://trojanpass@example.com:443?type=ws&path=%2Ft&sni=t.example.com#tj"
MIXED_LINKS = "\n".join([SS_LINK, VMESS_LINK, TROJAN_LINK])


@pytest.fixture()
def parser() -> SubscriptionParser:
    return SubscriptionParser(
        registry=default_registry(),
        user_agent="test/1.0",
        timeout=10.0,
    )


# --- fetch + parse via respx ---------------------------------------------- #


@respx.mock
async def test_fetch_and_parse_mixed_subscription(parser: SubscriptionParser) -> None:
    respx.get(SUB_URL).mock(
        return_value=httpx.Response(
            200,
            text=MIXED_LINKS,
            headers={
                "subscription-userinfo": "upload=1;download=2;total=3",
                "profile-update-interval": "6",
            },
        )
    )
    sub = await parser.fetch_and_parse(SUB_URL)
    types = {n.type for n in sub.nodes}
    assert ProxyType.SS in types
    assert ProxyType.VMESS in types
    assert ProxyType.TROJAN in types
    assert len(sub.nodes) == 3
    # upstream metadata preserved
    assert sub.subscription_userinfo == "upload=1;download=2;total=3"
    assert sub.profile_update_interval == 6
    assert sub.fetched_at_iso.endswith("Z")


@respx.mock
async def test_fetch_and_parse_base64_blob(parser: SubscriptionParser) -> None:
    blob = base64.b64encode(MIXED_LINKS.encode()).decode()
    respx.get(SUB_URL).mock(return_value=httpx.Response(200, text=blob))
    sub = await parser.fetch_and_parse(SUB_URL)
    assert len(sub.nodes) == 3


@respx.mock
async def test_fetch_raises_on_http_error(parser: SubscriptionParser) -> None:
    respx.get(SUB_URL).mock(return_value=httpx.Response(502))
    with pytest.raises(SubscriptionFetchError):
        await parser.fetch_and_parse(SUB_URL)


@respx.mock
async def test_fetch_raises_on_network_error(parser: SubscriptionParser) -> None:
    respx.get(SUB_URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(SubscriptionFetchError):
        await parser.fetch_and_parse(SUB_URL)


# --- parse_text edge cases ------------------------------------------------ #


def test_parse_text_rejects_empty(parser: SubscriptionParser) -> None:
    with pytest.raises(SubscriptionParseError):
        parser.parse_text("")


def test_parse_text_rejects_garbage(parser: SubscriptionParser) -> None:
    with pytest.raises(SubscriptionParseError):
        parser.parse_text("not a subscription at all")


def test_parse_text_skips_unparseable_lines(parser: SubscriptionParser) -> None:
    """A single bad line among good ones should not abort the whole parse."""
    body = f"garbage-no-scheme\n{SS_LINK}\nalso:::weird"
    sub = parser.parse_text(body)
    assert len(sub.nodes) == 1
    assert sub.nodes[0].type is ProxyType.SS


def test_parse_text_does_not_log_url(capsys: pytest.CaptureFixture[str]) -> None:
    """The orchestrator must never echo the URL into stdout/stderr."""
    p = SubscriptionParser(registry=default_registry(), user_agent="t", timeout=1.0)
    p.parse_text(SS_LINK)
    out = capsys.readouterr()
    assert "secret" not in out.out + out.err


async def test_fetch_rejects_non_http_url(parser: SubscriptionParser) -> None:
    with pytest.raises(SubscriptionFetchError):
        await parser.fetch_async("ftp://nope")
