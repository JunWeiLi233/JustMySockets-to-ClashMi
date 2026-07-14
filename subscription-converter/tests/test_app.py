"""HTTP-layer tests for the FastAPI app.

Uses FastAPI's TestClient. The upstream parser is monkeypatched so no real
network is involved. respx is used for the dynamic-update scenario to verify
the full fetch->parse->render->cache flow.
"""

from __future__ import annotations

import base64

import httpx
import pytest
import respx
import yaml
from fastapi.testclient import TestClient
from subscription_converter.app import create_app
from subscription_converter.config import Settings
from subscription_converter.network_guard import default_url_validator
from subscription_converter.subscription_parser import SubscriptionParser

__all__ = ()

SUB_URL = "https://sub.example.com/getsub.php?token=secret"

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
MIXED = "\n".join([SS_LINK, VMESS_LINK])


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """App with the upstream fetch stubbed to a fixed mixed subscription."""
    real = SubscriptionParser.fetch_and_parse

    async def stub(self: SubscriptionParser, url: str) -> object:
        return await real(self, url) if url.endswith("/dynamic") else self.parse_text(MIXED)

    monkeypatch.setattr(SubscriptionParser, "fetch_and_parse", stub)
    app = create_app(Settings(), url_validator=default_url_validator(resolve=False))
    with TestClient(app) as c:
        yield c


# --- basic endpoints ------------------------------------------------------ #


def test_root(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.text.strip() == "Subscription Converter Running"


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --- /clash --------------------------------------------------------------- #


def test_clash_returns_yaml(client: TestClient) -> None:
    r = client.get("/clash", params={"url": SUB_URL})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/yaml")
    doc = yaml.safe_load(r.text)
    assert "proxies" in doc and len(doc["proxies"]) >= 2
    # freshness header present
    assert r.headers.get("X-Subscription-Fetched-At", "").endswith("Z")


def test_clash_caches_upstream(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    orig = SubscriptionParser.fetch_and_parse

    async def counting(self: SubscriptionParser, url: str) -> object:
        calls["n"] += 1
        return await orig(self, url)

    monkeypatch.setattr(SubscriptionParser, "fetch_and_parse", counting)
    for _ in range(3):
        r = client.get("/clash", params={"url": SUB_URL})
        assert r.status_code == 200
    assert calls["n"] == 1, f"upstream fetched {calls['n']} times, expected 1"


def test_force_refresh_bypasses_cache(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    orig = SubscriptionParser.fetch_and_parse

    async def counting(self: SubscriptionParser, url: str) -> object:
        calls["n"] += 1
        return await orig(self, url)

    monkeypatch.setattr(SubscriptionParser, "fetch_and_parse", counting)
    client.get("/clash", params={"url": SUB_URL})
    client.get("/clash", params={"url": SUB_URL})  # cached
    client.get("/clash", params={"url": SUB_URL, "force_refresh": "true"})
    assert calls["n"] == 2


# --- 400 paths ------------------------------------------------------------ #


def test_missing_url_returns_400(client: TestClient) -> None:
    assert client.get("/clash").status_code == 400


def test_bad_scheme_returns_400(client: TestClient) -> None:
    r = client.get("/clash", params={"url": "ftp://nope"})
    assert r.status_code == 400


def test_parse_error_returns_400(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from subscription_converter.subscription_parser import SubscriptionParseError

    async def boom(self: SubscriptionParser, url: str) -> object:
        raise SubscriptionParseError("boom")

    monkeypatch.setattr(SubscriptionParser, "fetch_and_parse", boom)
    r = client.get("/clash", params={"url": SUB_URL})
    assert r.status_code == 400
    assert "conversion failed" in r.text


# --- allowed_hosts gating ------------------------------------------------- #


def test_disallowed_host_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings().with_overrides(allowed_hosts=("only-this.example.com",))
    app = create_app(
        settings,
        url_validator=default_url_validator(settings.allowed_hosts, resolve=False),
    )
    with TestClient(app) as c:
        r = c.get("/clash", params={"url": "https://other.example.com/x"})
        assert r.status_code == 400
        assert "not allowed" in r.text


# --- surge / sing-box placeholders ---------------------------------------- #


def test_surge_endpoint(client: TestClient) -> None:
    r = client.get("/surge", params={"url": SUB_URL})
    assert r.status_code == 200
    assert "[Proxy]" in r.text


def test_singbox_endpoint(client: TestClient) -> None:
    r = client.get("/sing-box", params={"url": SUB_URL})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    import json

    parsed = json.loads(r.text)
    assert "outbounds" in parsed


# --- dynamic update via respx (real fetch path) --------------------------- #


@respx.mock
def test_dynamic_upstream_change_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real upstream change is reflected after force_refresh."""
    respx.get(SUB_URL).mock(return_value=httpx.Response(200, text=MIXED))
    app = create_app(Settings(), url_validator=default_url_validator(resolve=False))
    with TestClient(app) as c:
        r1 = c.get("/clash", params={"url": SUB_URL})
        d1 = yaml.safe_load(r1.text)
        n1 = len(d1["proxies"])
        # upstream now returns only the ss link
        respx.get(SUB_URL).mock(return_value=httpx.Response(200, text=SS_LINK))
        r2 = c.get("/clash", params={"url": SUB_URL, "force_refresh": "true"})
        d2 = yaml.safe_load(r2.text)
        assert len(d2["proxies"]) < n1
