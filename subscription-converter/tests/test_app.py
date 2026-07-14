"""HTTP-layer tests for the FastAPI app.

Uses FastAPI's TestClient. The upstream parser is monkeypatched so no real
network is involved. respx is used for the dynamic-update scenario to verify
the full fetch->parse->render->cache flow.
"""

from __future__ import annotations

import base64
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
import respx
import yaml
from fastapi.testclient import TestClient
from subscription_converter.app import AppState, create_app
from subscription_converter.config import Settings
from subscription_converter.link_store import LinkStoreConfigurationError
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
LINK_SECRET_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode()


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


@pytest.fixture()
def persistent_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """App with encrypted durable links enabled on a temporary SQLite file."""

    async def stub(self: SubscriptionParser, url: str) -> object:
        return self.parse_text(MIXED)

    monkeypatch.setattr(SubscriptionParser, "fetch_and_parse", stub)
    settings = Settings().with_overrides(
        persistent_links_enabled=True,
        link_database_path=str(tmp_path / "links.sqlite3"),
        link_secret_key=LINK_SECRET_KEY,
        max_active_links=2,
        max_links_per_source=2,
        public_base_url="https://testserver",
    )
    app = create_app(settings, url_validator=default_url_validator(resolve=False))
    with TestClient(app) as c:
        yield c


# --- basic endpoints ------------------------------------------------------ #


def test_root(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "JMS Config Bridge" in r.text
    assert "Create permanent link" in r.text
    assert "Permanently close link" in r.text
    assert "/api/links" in r.text
    assert "https://sub.example.com" not in r.text


def test_root_has_strict_privacy_headers(client: TestClient) -> None:
    r = client.get("/")
    csp = r.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "connect-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert r.headers["cache-control"] == "private, no-store, max-age=0"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_docs_are_disabled_by_default(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["persistent_links"] == "disabled"


def test_capacity_reports_disabled_by_default(client: TestClient) -> None:
    r = client.get("/api/capacity")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "enabled": False,
        "accepting": False,
        "active": 0,
        "limit": 0,
        "remaining": 0,
    }
    assert r.headers["cache-control"] == "private, no-store, max-age=0"


# --- durable opaque links ------------------------------------------------- #


def test_persistent_link_create_fetch_and_close_end_to_end(
    persistent_client: TestClient,
) -> None:
    created = persistent_client.post(
        "/api/links",
        json={"url": SUB_URL, "format": "clash"},
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["status"] == "ok"
    assert payload["expires_at"] is None
    assert payload["nodes"] == 2
    assert payload["subscription_url"].startswith("https://testserver/s/")
    assert len(payload["manage_key"]) == 43
    assert SUB_URL not in created.text
    assert created.headers["cache-control"] == "private, no-store, max-age=0"

    path = urlsplit(payload["subscription_url"]).path
    rendered = persistent_client.get(path)
    assert rendered.status_code == 200
    assert rendered.headers["content-type"].startswith("application/yaml")
    assert rendered.headers["cache-control"] == "private, no-store, max-age=0"
    assert len(yaml.safe_load(rendered.text)["proxies"]) == 2

    health = persistent_client.get("/health").json()
    assert health["persistent_links"] == "ready"
    assert health["active_links"] == 1

    closed = persistent_client.post(
        "/api/links/close",
        json={"manage_key": payload["manage_key"]},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert persistent_client.get(path).status_code == 404
    assert persistent_client.get("/api/capacity").json()["remaining"] == 2


def test_access_and_management_tokens_have_separate_authority(
    persistent_client: TestClient,
) -> None:
    payload = persistent_client.post(
        "/api/links",
        json={"url": SUB_URL, "format": "clash"},
    ).json()
    access_token = urlsplit(payload["subscription_url"]).path.rsplit("/", 1)[-1]

    assert persistent_client.get(f"/s/{payload['manage_key']}").status_code == 404
    cannot_close = persistent_client.post(
        "/api/links/close",
        json={"manage_key": access_token},
    )
    assert cannot_close.status_code == 404
    assert persistent_client.get(f"/s/{access_token}").status_code == 200


def test_capacity_closes_creation_but_existing_links_continue(
    persistent_client: TestClient,
) -> None:
    urls: list[str] = []
    for index in range(2):
        response = persistent_client.post(
            "/api/links",
            json={"url": f"{SUB_URL}&slot={index}", "format": "clash"},
        )
        assert response.status_code == 201
        urls.append(urlsplit(response.json()["subscription_url"]).path)

    capacity = persistent_client.get("/api/capacity").json()
    assert capacity["accepting"] is False
    assert capacity["remaining"] == 0
    rejected = persistent_client.post(
        "/api/links",
        json={"url": f"{SUB_URL}&slot=third", "format": "clash"},
    )
    assert rejected.status_code == 503
    assert rejected.json()["code"] == "capacity_reached"
    assert rejected.headers["retry-after"] == "3600"
    assert all(persistent_client.get(path).status_code == 200 for path in urls)


def test_persistent_link_mutations_reject_cross_site_browser_requests(
    persistent_client: TestClient,
) -> None:
    create = persistent_client.post(
        "/api/links",
        headers={"Sec-Fetch-Site": "cross-site"},
        json={"url": SUB_URL, "format": "clash"},
    )
    close = persistent_client.post(
        "/api/links/close",
        headers={"Sec-Fetch-Site": "cross-site"},
        json={"manage_key": "x" * 43},
    )
    assert create.status_code == 403
    assert close.status_code == 403
    assert create.json()["code"] == "cross_site"
    assert close.json()["code"] == "cross_site"


def test_persistent_link_requires_https(persistent_client: TestClient) -> None:
    response = persistent_client.post(
        "/api/links",
        json={"url": "http://sub.example.com/getsub", "format": "clash"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "https_required"


def test_legacy_url_endpoints_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def stub(self: SubscriptionParser, url: str) -> object:
        return self.parse_text(MIXED)

    monkeypatch.setattr(SubscriptionParser, "fetch_and_parse", stub)
    settings = Settings().with_overrides(allow_legacy_url_endpoints=False)
    app = create_app(settings, url_validator=default_url_validator(resolve=False))
    with TestClient(app) as local_client:
        response = local_client.get("/clash", params={"url": SUB_URL})
    assert response.status_code == 410
    assert "create a private /s/ link" in response.text


@pytest.mark.parametrize(
    "public_base_url",
    ["", "http://public.example.com", "https://user:pass@example.com", "https://example.com/path"],
)
def test_persistent_links_fail_closed_for_unsafe_public_base_url(
    tmp_path: Path,
    public_base_url: str,
) -> None:
    settings = Settings().with_overrides(
        persistent_links_enabled=True,
        link_database_path=str(tmp_path / "links.sqlite3"),
        link_secret_key=LINK_SECRET_KEY,
        public_base_url=public_base_url,
    )
    with pytest.raises(LinkStoreConfigurationError, match="PUBLIC_BASE_URL"):
        AppState(settings, url_validator=default_url_validator(resolve=False))


# --- /clash --------------------------------------------------------------- #


def test_clash_returns_yaml(client: TestClient) -> None:
    r = client.get("/clash", params={"url": SUB_URL})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/yaml")
    doc = yaml.safe_load(r.text)
    assert "proxies" in doc and len(doc["proxies"]) >= 2
    # freshness header present
    assert r.headers.get("X-Subscription-Fetched-At", "").endswith("Z")
    assert r.headers["cache-control"] == "private, no-store, max-age=0"
    assert r.headers["pragma"] == "no-cache"


def test_private_check_returns_metadata_only(client: TestClient) -> None:
    r = client.post(
        "/api/check",
        json={"url": SUB_URL, "format": "clash", "force_refresh": True},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["nodes"] == 2
    assert SUB_URL not in r.text
    assert "proxies" not in r.text
    assert r.headers["cache-control"] == "private, no-store, max-age=0"


def test_private_check_requires_https(client: TestClient) -> None:
    r = client.post(
        "/api/check",
        json={"url": "http://sub.example.com/getsub", "format": "clash"},
    )
    assert r.status_code == 400
    assert r.json()["message"] == "an HTTPS subscription URL is required"


def test_private_check_rejects_cross_site_browser_requests(client: TestClient) -> None:
    r = client.post(
        "/api/check",
        headers={"Sec-Fetch-Site": "cross-site"},
        json={"url": SUB_URL, "format": "clash"},
    )
    assert r.status_code == 403
    assert r.json()["message"] == "cross-site checks are not allowed"


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
