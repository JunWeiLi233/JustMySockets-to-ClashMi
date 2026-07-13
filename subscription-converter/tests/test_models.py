"""Tests for the provider-independent domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from subscription_converter.models import (
    ProxyNode,
    ProxyType,
    Subscription,
    TlsOptions,
    TransportOptions,
)


def _ss_node(**overrides: object) -> ProxyNode:
    base: dict[str, object] = {
        "type": ProxyType.SS,
        "name": "test-ss",
        "server": "ss.example.com",
        "port": 8388,
        "cipher": "aes-256-gcm",
        "password": "secret",
    }
    base.update(overrides)
    return ProxyNode.model_validate(base)


# --------------------------------------------------------------------------- #
# ProxyNode validation
# --------------------------------------------------------------------------- #


def test_proxy_node_minimal_construction() -> None:
    node = _ss_node()
    assert node.type is ProxyType.SS
    assert node.server == "ss.example.com"
    assert node.port == 8388
    assert node.tls.enabled is False
    assert node.transport.network == "tcp"


def test_proxy_node_rejects_empty_server() -> None:
    with pytest.raises(ValidationError):
        _ss_node(server="   ")


def test_proxy_node_rejects_out_of_range_port() -> None:
    with pytest.raises(ValidationError):
        _ss_node(port=0)
    with pytest.raises(ValidationError):
        _ss_node(port=70000)


def test_proxy_node_extra_fields_ignored() -> None:
    """Real-world subscriptions carry unknown keys; we must not reject them."""
    node = ProxyNode.model_validate(
        {
            "type": "ss",
            "name": "x",
            "server": "h",
            "port": 1,
            "unknown_future_field": {"whatever": 42},
        }
    )
    assert node.server == "h"
    assert not hasattr(node, "unknown_future_field")


def test_safe_name_falls_back_when_empty() -> None:
    node = _ss_node(name="")
    assert node.safe_name == "ss-ss.example.com-8388"


def test_safe_name_strips_whitespace() -> None:
    node = _ss_node(name="  trimmed  ")
    assert node.safe_name == "trimmed"


# --------------------------------------------------------------------------- #
# TLS / transport options
# --------------------------------------------------------------------------- #


def test_tls_options_defaults() -> None:
    tls = TlsOptions()
    assert tls.enabled is False
    assert tls.alpn == []
    assert tls.reality_public_key is None


def test_transport_options_defaults() -> None:
    t = TransportOptions()
    assert t.network == "tcp"
    assert t.path is None


# --------------------------------------------------------------------------- #
# Subscription
# --------------------------------------------------------------------------- #


def test_subscription_is_frozen() -> None:
    sub = Subscription(nodes=(_ss_node(),))
    with pytest.raises(ValidationError):
        sub.nodes = ()  # type: ignore[misc]


def test_subscription_profile_update_interval_parses() -> None:
    sub = Subscription(
        nodes=(),
        upstream_headers={"profile-update-interval": "6"},
    )
    assert sub.profile_update_interval == 6


def test_subscription_profile_update_interval_none_when_absent() -> None:
    assert Subscription(nodes=()).profile_update_interval is None


def test_subscription_profile_update_interval_invalid_returns_none() -> None:
    sub = Subscription(
        nodes=(),
        upstream_headers={"profile-update-interval": "not-a-number"},
    )
    assert sub.profile_update_interval is None


def test_subscription_userinfo_passthrough() -> None:
    sub = Subscription(
        nodes=(),
        upstream_headers={"subscription-userinfo": "upload=1;download=2;total=3"},
    )
    assert sub.subscription_userinfo == "upload=1;download=2;total=3"
