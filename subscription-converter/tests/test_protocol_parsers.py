"""Tests for the concrete protocol parsers.

Uses realistic (fake-credential) URIs for each protocol. All credentials here
are fabricated and safe to ship in the repo.
"""

from __future__ import annotations

import base64
import json

import pytest
from subscription_converter.models import ProxyType
from subscription_converter.parser_port import ParserError
from subscription_converter.parsers import (
    Hysteria2Parser,
    ShadowsocksParser,
    TrojanParser,
    TuicParser,
    VlessParser,
    VmessParser,
)

__all__ = ()


# --- fixtures (fake creds) ------------------------------------------------- #

SS_SIP002 = (
    "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQxMjM=@ss.example.com:8388"
    "/?plugin=obfs-local%3Bobfs%3Dtls%3Bobfs-host%3Dbing.com#ss-obfs-tls"
)


def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def _vmess_uri(cfg: dict[str, object]) -> str:
    return "vmess://" + _b64(json.dumps(cfg))


VMESS_WS_TLS = _vmess_uri(
    {
        "v": "2",
        "ps": "vmess-ws-tls",
        "add": "vm.example.com",
        "port": "443",
        "id": "b831381d-6324-4d53-ad4f-8cda48b30811",
        "aid": "0",
        "net": "ws",
        "type": "none",
        "host": "cdn.example.com",
        "path": "/ray",
        "tls": "tls",
        "sni": "cdn.example.com",
        "alpn": "h2,http/1.1",
    }
)

VLESS_REALITY = (
    "vless://a3f5b8a1-2b3c-4d5e-6f70-1234567890ab@vless.example.com:443"
    "?encryption=none&security=reality&sni=www.microsoft.com"
    "&fp=chrome&pbk=ZBD8j7bFPVdK5SxN7KH2k3u6Vq8wXyZabcd12345678"
    "&sid=ab12cd34&flow=xtls-rprx-vision&type=tcp#vless-reality"
)

TROJAN_WS = (
    "trojan://trojanpass@example.com:443?type=ws&path=%2Ftrojan"
    "&host=trojan.example.com&sni=trojan.example.com#trojan-ws"
)

HY2 = (
    "hysteria2://hy2password@hy2.example.com:443?sni=hy2.example.com&insecure=0"
    "&obfs=salamander&obfs-password=obfspw&up=50%20Mbps&down=200%20Mbps#hy2-node"
)
HY2_ALIAS = HY2.replace("hysteria2://", "hy2://")

TUIC = (
    "tuic://b831381d-6324-4d53-ad4f-8cda48b30811:tuicpw@tuic.example.com:443"
    "?sni=tuic.example.com&congestion_control=bbr&udp_relay_mode=native#tuic-node"
)


# --- ss -------------------------------------------------------------------- #


def test_ss_sip002_parses_with_obfs_plugin() -> None:
    node = ShadowsocksParser().parse(SS_SIP002)
    assert node.type is ProxyType.SS
    assert node.server == "ss.example.com"
    assert node.port == 8388
    assert node.cipher == "aes-256-gcm"
    assert node.password == "password123"
    assert node.plugin == "obfs"  # normalised from obfs-local
    assert node.name == "ss-obfs-tls"


def test_ss_legacy_base64_parses() -> None:
    body = _b64("aes-256-gcm:legacyPass@1.2.3.4:8388")
    node = ShadowsocksParser().parse("ss://" + body)
    assert node.server == "1.2.3.4"
    assert node.cipher == "aes-256-gcm"
    assert node.password == "legacyPass"


def test_ss_rejects_non_ss() -> None:
    with pytest.raises(ParserError):
        ShadowsocksParser().parse("vmess://x")


# --- vmess ----------------------------------------------------------------- #


def test_vmess_parses_ws_tls_transport() -> None:
    node = VmessParser().parse(VMESS_WS_TLS)
    assert node.type is ProxyType.VMESS
    assert node.server == "vm.example.com"
    assert node.uuid == "b831381d-6324-4d53-ad4f-8cda48b30811"
    assert node.transport.network == "ws"
    assert node.transport.path == "/ray"
    assert node.tls.enabled is True
    assert node.tls.sni == "cdn.example.com"
    assert node.tls.alpn == ["h2", "http/1.1"]


def test_vmess_rejects_bad_json() -> None:
    with pytest.raises(ParserError):
        VmessParser().parse("vmess://" + _b64("not json"))


# --- vless ----------------------------------------------------------------- #


def test_vless_parses_reality_fields() -> None:
    node = VlessParser().parse(VLESS_REALITY)
    assert node.type is ProxyType.VLESS
    assert node.uuid == "a3f5b8a1-2b3c-4d5e-6f70-1234567890ab"
    assert node.flow == "xtls-rprx-vision"
    assert node.tls.reality_public_key == "ZBD8j7bFPVdK5SxN7KH2k3u6Vq8wXyZabcd12345678"
    assert node.tls.reality_short_id == "ab12cd34"
    assert node.tls.fingerprint == "chrome"


# --- trojan ---------------------------------------------------------------- #


def test_trojan_parses_ws_transport() -> None:
    node = TrojanParser().parse(TROJAN_WS)
    assert node.type is ProxyType.TROJAN
    assert node.password == "trojanpass"
    assert node.transport.network == "ws"
    assert node.transport.path == "/trojan"
    assert node.tls.sni == "trojan.example.com"


# --- hysteria2 ------------------------------------------------------------- #


def test_hysteria2_parses_obfs_and_bandwidth() -> None:
    node = Hysteria2Parser().parse(HY2)
    assert node.type is ProxyType.HYSTERIA2
    assert node.password == "hy2password"
    assert node.obfs == "salamander"
    assert node.obfs_password == "obfspw"
    assert node.up == "50 Mbps"
    assert node.down == "200 Mbps"
    assert node.tls.sni == "hy2.example.com"


def test_hy2_alias_scheme() -> None:
    """The hy2:// alias should parse via the hysteria2 parser."""
    node = Hysteria2Parser().parse(HY2_ALIAS)
    assert node.type is ProxyType.HYSTERIA2
    assert node.server == "hy2.example.com"


# --- tuic ------------------------------------------------------------------ #


def test_tuic_parses_uuid_and_password() -> None:
    node = TuicParser().parse(TUIC)
    assert node.type is ProxyType.TUIC
    assert node.uuid == "b831381d-6324-4d53-ad4f-8cda48b30811"
    assert node.password == "tuicpw"
    assert node.congestion_controller == "bbr"
    assert node.udp_relay_mode == "native"


# --- registry alias coverage ---------------------------------------------- #


def test_all_parsers_implement_protocol() -> None:
    from subscription_converter.parser_port import ProtocolParser

    for parser in [
        ShadowsocksParser(),
        VmessParser(),
        VlessParser(),
        TrojanParser(),
        Hysteria2Parser(),
        TuicParser(),
    ]:
        assert isinstance(parser, ProtocolParser)
