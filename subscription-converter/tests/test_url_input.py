r"""Tests for forgiving subscription-URL input handling.

These reproduce the exact user-facing bugs that motivated the feature:

1. Stray backslashes inserted by the shell
   (``https://x\?service\=1\&id=2``).
2. A leading ``%20`` from ``curl %20https...``.
3. A pre-encoded URL (user encoded it themselves).
4. An unencoded URL pasted raw with ``?``/``&``.
"""

from __future__ import annotations

import pytest
from subscription_converter.url_input import (
    InvalidSubscriptionURL,
    normalize_subscription_url,
)

__all__ = ()

CLEAN = (
    "https://jmssub.net/members/getsub.php?service=123456&id=00000000-0000-4000-8000-000000000000"
)


# --- normalize_subscription_url: unit-level -------------------------------- #


def test_clean_url_passes_through() -> None:
    assert normalize_subscription_url(CLEAN) == CLEAN


def test_strips_stray_backslashes_before_punctuation() -> None:
    """The exact bug: shell-escaped '?', '=', '&', '/'."""
    messy = r"https://jmssub.net/members/getsub.php\?service\=123456\&id\=00000000"
    assert (
        normalize_subscription_url(messy)
        == "https://jmssub.net/members/getsub.php?service=123456&id=00000000"
    )


def test_strips_leading_percent20_space() -> None:
    """Residue of `curl %20https...`."""
    assert normalize_subscription_url("%20https://example.com/x") == "https://example.com/x"
    assert normalize_subscription_url("  https://example.com/x ") == "https://example.com/x"


def test_decodes_pre_encoded_url_once() -> None:
    """User encoded the URL themselves; we undo exactly one layer."""
    encoded = (
        "https%3A%2F%2Fjmssub.net%2Fmembers%2Fgetsub.php%3Fservice%3D123456"
        "%26id%3D00000000-0000-4000-8000-000000000000"
    )
    assert normalize_subscription_url(encoded) == CLEAN


def test_does_not_decode_non_url_encoded_text() -> None:
    """Text that merely contains a percent sign but isn't an encoded URL is left alone."""
    assert normalize_subscription_url("https://example.com/a%2") == "https://example.com/a%2"


def test_rejects_empty() -> None:
    with pytest.raises(InvalidSubscriptionURL):
        normalize_subscription_url("")
    with pytest.raises(InvalidSubscriptionURL):
        normalize_subscription_url("   ")


def test_rejects_non_http_scheme() -> None:
    with pytest.raises(InvalidSubscriptionURL):
        normalize_subscription_url("ftp://example.com/x")
    with pytest.raises(InvalidSubscriptionURL):
        normalize_subscription_url("not a url at all")


def test_rejects_none() -> None:
    with pytest.raises(InvalidSubscriptionURL):
        normalize_subscription_url(None)  # type: ignore[arg-type]


def test_combined_messy_input_all_fixes() -> None:
    """Backslashes + leading space + pre-encoding all at once."""
    messy = "  %20https%3A%2F%2Fx.net%2Fs\\%3Fa\\%3D1  "
    # After stripping space/backslashes we have an encoded URL; decode once.
    result = normalize_subscription_url(messy)
    assert result.startswith("https://")


# --- end-to-end via the HTTP layer ---------------------------------------- #


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    """App with the upstream fetch stubbed so no real network is used."""
    from fastapi.testclient import TestClient
    from subscription_converter.app import create_app
    from subscription_converter.config import Settings
    from subscription_converter.subscription_parser import SubscriptionParser

    SS_LINK = "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQxMjM=@ss.example.com:8388#node"

    async def stub(self: SubscriptionParser, url: str) -> object:
        _ = url  # the normalized URL is what we'd fetch upstream
        return self.parse_text(SS_LINK)

    monkeypatch.setattr(SubscriptionParser, "fetch_and_parse", stub)
    from subscription_converter.network_guard import default_url_validator

    app = create_app(Settings(), url_validator=default_url_validator(resolve=False))
    with TestClient(app) as c:
        yield c


def test_endpoint_accepts_raw_unencoded_url(client) -> None:  # type: ignore[no-untyped-def]
    """User pastes the URL raw (with unencoded ? and &); it still works."""
    r = client.get("/clash", params={"url": CLEAN})
    assert r.status_code == 200, r.text
    assert "proxies:" in r.text


def test_endpoint_accepts_pre_encoded_url(client) -> None:  # type: ignore[no-untyped-def]
    encoded = "https%3A%2F%2Fjmssub.net%2Fgetsub.php%3Fservice%3D1%26id%3Dabc"
    r = client.get("/clash", params={"url": encoded})
    assert r.status_code == 200, r.text


def test_endpoint_still_supports_force_refresh(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/clash", params={"url": CLEAN, "force_refresh": "true"})
    assert r.status_code == 200, r.text


def test_endpoint_400_on_missing_url(client) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/clash").status_code == 400


def test_endpoint_400_on_non_http(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/clash", params={"url": "ftp://nope"})
    assert r.status_code == 400
