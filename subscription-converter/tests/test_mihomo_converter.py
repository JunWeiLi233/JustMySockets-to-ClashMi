"""Tests for the Mihomo converter.

Renders real nodes (produced by the parser) into Mihomo YAML, round-trips the
output through PyYAML, and asserts the required structural properties and
per-protocol field correctness.
"""

from __future__ import annotations

import base64
import json

import pytest
import yaml
from subscription_converter.converter_registry import get_converter
from subscription_converter.converters import ConversionError
from subscription_converter.converters.mihomo import MihomoConverter
from subscription_converter.models import ProxyNode, ProxyType
from subscription_converter.parsers import default_registry
from subscription_converter.subscription_parser import SubscriptionParser

__all__ = ()


# --- realistic mixed subscription body (fake creds) ------------------------ #

SS_LINK = (
    "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQxMjM=@ss.example.com:8388"
    "/?plugin=obfs-local%3Bobfs%3Dtls%3Bobfs-host%3Dbing.com#ss-obfs-tls"
)
VMESS_LINK = (
    "vmess://"
    + base64.b64encode(
        json.dumps(
            {
                "v": "2",
                "ps": "vmess-ws-tls",
                "add": "vm.example.com",
                "port": "443",
                "id": "b831381d-6324-4d53-ad4f-8cda48b30811",
                "aid": "0",
                "net": "ws",
                "host": "cdn.example.com",
                "path": "/ray",
                "tls": "tls",
                "sni": "cdn.example.com",
            }
        ).encode()
    ).decode()
)
VLESS_LINK = (
    "vless://a3f5b8a1-2b3c-4d5e-6f70-1234567890ab@vless.example.com:443"
    "?security=reality&sni=www.microsoft.com&fp=chrome"
    "&pbk=ZBD8j7bFPVdK5SxN7KH2k3u6Vq8wXyZabcd12345678&sid=ab12cd34"
    "&flow=xtls-rprx-vision&type=tcp#vless-reality"
)
TROJAN_LINK = "trojan://trojanpass@example.com:443?type=ws&path=%2Ftrojan&host=trojan.example.com&sni=trojan.example.com#trojan-ws"
HY2_LINK = (
    "hysteria2://hy2password@hy2.example.com:443?sni=hy2.example.com"
    "&obfs=salamander&obfs-password=obfspw&up=50%20Mbps&down=200%20Mbps#hy2-node"
)
TUIC_LINK = (
    "tuic://b831381d-6324-4d53-ad4f-8cda48b30811:tuicpw@tuic.example.com:443"
    "?sni=tuic.example.com&congestion_control=bbr&udp_relay_mode=native#tuic-node"
)
MIXED = "\n".join([SS_LINK, VMESS_LINK, VLESS_LINK, TROJAN_LINK, HY2_LINK, TUIC_LINK])


@pytest.fixture(scope="module")
def parser() -> SubscriptionParser:
    return SubscriptionParser(registry=default_registry(), user_agent="test/1.0", timeout=10.0)


@pytest.fixture(scope="module")
def nodes(parser: SubscriptionParser) -> tuple[ProxyNode, ...]:
    return parser.parse_text(MIXED).nodes


@pytest.fixture(scope="module")
def rendered(nodes: tuple[ProxyNode, ...]) -> dict[str, object]:
    conv = MihomoConverter(test_url="https://www.gstatic.com/generate_204", test_interval=300)
    yaml_text = conv.render(nodes)
    return yaml.safe_load(yaml_text)


# --- structural tests ----------------------------------------------------- #


def test_yaml_is_valid_and_has_top_level_keys(rendered: dict[str, object]) -> None:
    for key in ("proxies", "proxy-groups", "rules", "dns"):
        assert key in rendered


def test_proxy_groups_include_auto_select_direct(rendered: dict[str, object]) -> None:
    groups = {g["name"]: g for g in rendered["proxy-groups"]}  # type: ignore[index]
    assert "AUTO" in groups
    assert groups["AUTO"]["type"] == "url-test"  # type: ignore[index]
    assert "SELECT" in groups
    assert "DIRECT" in groups["SELECT"]["proxies"]  # type: ignore[index]


def test_match_rule_to_select(rendered: dict[str, object]) -> None:
    assert "MATCH,SELECT" in rendered["rules"]


def test_proxy_names_are_unique(rendered: dict[str, object]) -> None:
    names = [p["name"] for p in rendered["proxies"]]  # type: ignore[index]
    assert len(names) == len(set(names))


def test_proxies_have_required_fields(rendered: dict[str, object]) -> None:
    for p in rendered["proxies"]:  # type: ignore[index]
        for field in ("name", "type", "server", "port"):
            assert field in p
        assert isinstance(p["port"], int) and 0 < p["port"] <= 65535


def test_all_protocol_types_present(rendered: dict[str, object]) -> None:
    types = {p["type"] for p in rendered["proxies"]}  # type: ignore[index]
    assert {"ss", "vmess", "vless", "trojan", "hysteria2", "tuic"} <= types


# --- per-protocol field correctness --------------------------------------- #


def test_ss_obfs_plugin_normalised(rendered: dict[str, object]) -> None:
    ss = next(p for p in rendered["proxies"] if p["type"] == "ss")  # type: ignore[index]
    assert ss["plugin"] == "obfs"  # type: ignore[index]
    assert ss["plugin-opts"]["mode"] == "tls"  # type: ignore[index]


def test_vmess_type_not_overwritten_by_transport(rendered: dict[str, object]) -> None:
    """Regression: type must be 'vmess', NOT 'ws'; ws options go under ws-opts."""
    vmess = next(p for p in rendered["proxies"] if p["name"] == "vmess-ws-tls")  # type: ignore[index]
    assert vmess["type"] == "vmess"  # type: ignore[index]
    assert vmess["network"] == "ws"  # type: ignore[index]
    assert vmess["ws-opts"]["path"] == "/ray"  # type: ignore[index]
    assert vmess["ws-opts"]["headers"]["Host"] == "cdn.example.com"  # type: ignore[index]


def test_vless_reality_fields(rendered: dict[str, object]) -> None:
    vless = next(p for p in rendered["proxies"] if p["type"] == "vless")  # type: ignore[index]
    assert vless["flow"] == "xtls-rprx-vision"  # type: ignore[index]
    assert vless["reality-opts"]["public-key"]  # type: ignore[index]
    assert vless["client-fingerprint"] == "chrome"  # type: ignore[index]


def test_hysteria2_obfs_fields(rendered: dict[str, object]) -> None:
    hy2 = next(p for p in rendered["proxies"] if p["type"] == "hysteria2")  # type: ignore[index]
    assert hy2["obfs"] == "salamander"  # type: ignore[index]
    assert hy2["obfs-password"] == "obfspw"  # type: ignore[index]
    assert hy2["servername"] == "hy2.example.com"  # type: ignore[index]


def test_tuic_fields(rendered: dict[str, object]) -> None:
    tuic = next(p for p in rendered["proxies"] if p["type"] == "tuic")  # type: ignore[index]
    assert tuic["congestion-controller"] == "bbr"  # type: ignore[index]
    assert tuic["udp-relay-mode"] == "native"  # type: ignore[index]


def test_trojan_type_preserved(rendered: dict[str, object]) -> None:
    trojan = next(p for p in rendered["proxies"] if p["name"] == "trojan-ws")  # type: ignore[index]
    assert trojan["type"] == "trojan"  # type: ignore[index]


# --- dns + error paths ---------------------------------------------------- #


def test_dns_block_is_configurable() -> None:
    conv = MihomoConverter(
        test_url="x",
        test_interval=1,
        dns_nameserver=("https://resolver.example/dns-query",),
        dns_bootstrap=("9.9.9.9",),
        dns_ipv6=True,
    )
    dns = conv.build_dns()
    assert dns["nameserver"] == ["https://resolver.example/dns-query"]
    assert dns["default-nameserver"] == ["9.9.9.9"]
    assert dns["ipv6"] is True


def test_render_raises_when_no_renderable_proxies() -> None:
    # ss node missing password -> not renderable
    bad = ProxyNode(type=ProxyType.SS, name="x", server="h", port=1, cipher="aes-256-gcm")
    conv = MihomoConverter(test_url="x", test_interval=1)
    with pytest.raises(ConversionError):
        conv.render([bad])


def test_duplicate_proxy_names_deduplicated() -> None:
    a = ProxyNode(type=ProxyType.SS, name="dup", server="h1", port=1, cipher="c", password="p")
    b = ProxyNode(type=ProxyType.SS, name="dup", server="h2", port=2, cipher="c", password="p")
    conv = MihomoConverter(test_url="x", test_interval=1)
    proxies = conv.build_proxies([a, b])
    names = [p["name"] for p in proxies]
    assert len(names) == len(set(names))


def test_registry_get_returns_mihomo_converter() -> None:
    conv = get_converter("clash", test_url="x", test_interval=1)
    assert conv.media_type == "application/yaml"
    assert get_converter("mihomo", test_url="x", test_interval=1).name == "clash"


def test_registry_unknown_format_raises() -> None:
    with pytest.raises(ConversionError):
        get_converter("nope")
