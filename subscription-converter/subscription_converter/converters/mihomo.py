"""Mihomo / Clash Meta YAML converter.

Renders a list of :class:`~subscription_converter.models.ProxyNode` into a
complete, valid Mihomo configuration (proxies, proxy-groups, rules, dns).

Field names follow the official Mihomo documentation:
- ``servername`` for SNI (not ``sni``)
- ``client-fingerprint`` for uTLS
- ``reality-opts.public-key`` / ``reality-opts.short-id``
- ``ws-opts`` / ``grpc-opts`` / ``h2-opts`` (transport never overwrites ``type``)
- ``plugin: obfs`` (not ``obfs-local``)
- hysteria2: ``obfs: salamander`` + ``obfs-password``
"""

from __future__ import annotations

from collections.abc import Iterable

import yaml

from subscription_converter.converters import BaseConverter, ConversionError
from subscription_converter.models import ProxyNode, ProxyType, TlsOptions, TransportOptions

__all__ = ["MihomoConverter", "node_to_mihomo"]


# --------------------------------------------------------------------------- #
# Shared render helpers
# --------------------------------------------------------------------------- #


def _tls_dict(tls: TlsOptions) -> dict[str, object]:
    out: dict[str, object] = {}
    if tls.enabled:
        out["tls"] = True
    if tls.sni:
        out["servername"] = tls.sni
    if tls.alpn:
        out["alpn"] = list(tls.alpn)
    if tls.skip_cert_verify:
        out["skip-cert-verify"] = True
    if tls.fingerprint:
        out["client-fingerprint"] = tls.fingerprint
    if tls.reality_public_key:
        out["reality-opts"] = {
            "public-key": tls.reality_public_key,
            "short-id": tls.reality_short_id or "",
        }
    return out


def _transport_dict(t: TransportOptions) -> dict[str, object]:
    """Build the transport option block.

    Mihomo expects ``network`` at the proxy level plus a ``ws-opts`` /
    ``grpc-opts`` / ``h2-opts`` sub-block. A top-level ``type`` must NOT be
    emitted here — that key belongs to the protocol and would overwrite it.
    """
    if t.network in {"tcp", ""}:
        return {}
    out: dict[str, object] = {"network": t.network}
    if t.network == "ws":
        ws: dict[str, object] = {}
        if t.path:
            ws["path"] = t.path
        if t.host:
            ws["headers"] = {"Host": t.host}
        if ws:
            out["ws-opts"] = ws
    elif t.network == "grpc":
        if t.grpc_service_name:
            out["grpc-opts"] = {"grpc-service-name": t.grpc_service_name}
    elif t.network == "h2":
        h2: dict[str, object] = {}
        if t.path:
            h2["path"] = t.path
        if t.host:
            h2["host"] = [t.host]
        if h2:
            out["h2-opts"] = h2
    return out


def _ss_plugin(plugin: str | None, opts: str | None) -> dict[str, object]:
    if not plugin:
        return {}
    out: dict[str, object] = {"plugin": plugin}
    if opts:
        parsed = {
            k.strip(): v.strip()
            for k, v in (pair.split("=", 1) for pair in opts.split(";") if "=" in pair)
        }
        norm: dict[str, object] = {}
        if "obfs" in parsed:
            norm["mode"] = parsed["obfs"]
        if "obfs-host" in parsed:
            norm["host"] = parsed["obfs-host"]
        if "mode" in parsed:
            norm["mode"] = parsed["mode"]
        if "host" in parsed:
            norm["host"] = parsed["host"]
        if norm:
            out["plugin-opts"] = norm
    return out


def node_to_mihomo(node: ProxyNode) -> dict[str, object] | None:
    """Render a single node as a Mihomo proxy dict, or ``None`` if unsupported."""
    base: dict[str, object] = {
        "name": node.safe_name,
        "type": node.type.value,
        "server": node.server,
        "port": node.port,
    }

    if node.type == ProxyType.SS:
        if not node.cipher or not node.password:
            return None
        base.update({"cipher": node.cipher, "password": node.password})
        base.update(_ss_plugin(node.plugin, node.plugin_opts))
        if node.udp:
            base["udp"] = True
        return base

    if node.type == ProxyType.SSR:
        if not node.cipher or not node.password:
            return None
        base.update(
            {
                "cipher": node.cipher,
                "password": node.password,
                "obfs": node.ssr_obfs or "plain",
                "protocol": node.ssr_protocol or "origin",
            }
        )
        if node.ssr_protocol_param:
            base["protocol-param"] = node.ssr_protocol_param
        return base

    if node.type == ProxyType.VMESS:
        if not node.uuid:
            return None
        base.update({"uuid": node.uuid, "alterId": node.alter_id, "cipher": node.cipher or "auto"})
        base.update(_tls_dict(node.tls))
        base.update(_transport_dict(node.transport))
        if node.udp:
            base["udp"] = True
        return base

    if node.type == ProxyType.VLESS:
        if not node.uuid:
            return None
        base.update({"uuid": node.uuid})
        if node.flow:
            base["flow"] = node.flow
        base.update(_tls_dict(node.tls))
        base.update(_transport_dict(node.transport))
        if node.udp:
            base["udp"] = True
        return base

    if node.type == ProxyType.TROJAN:
        if not node.password:
            return None
        base.update({"password": node.password})
        base.update(_tls_dict(node.tls))
        base.update(_transport_dict(node.transport))
        if node.udp:
            base["udp"] = True
        return base

    if node.type == ProxyType.HYSTERIA2:
        if not node.password:
            return None
        base.update({"password": node.password})
        if node.obfs:
            base["obfs"] = node.obfs
            if node.obfs_password:
                base["obfs-password"] = node.obfs_password
        if node.up:
            base["up"] = node.up
        if node.down:
            base["down"] = node.down
        base.update(_tls_dict(node.tls))
        return base

    if node.type == ProxyType.HYSTERIA:
        base.update({"auth-str": node.password or ""})
        if node.up:
            base["up"] = node.up
        if node.down:
            base["down"] = node.down
        base.update(_tls_dict(node.tls))
        if node.obfs:
            base["obfs"] = node.obfs
            if node.obfs_password:
                base["obfs-password"] = node.obfs_password
        return base

    if node.type == ProxyType.TUIC:
        if not node.uuid:
            return None
        base.update({"uuid": node.uuid, "password": node.password or ""})
        if node.congestion_controller:
            base["congestion-controller"] = node.congestion_controller
        if node.udp_relay_mode:
            base["udp-relay-mode"] = node.udp_relay_mode
        base.update(_tls_dict(node.tls))
        return base

    return None


class MihomoConverter(BaseConverter):
    """Render a complete Clash Meta / Mihomo configuration."""

    name = "clash"
    media_type = "application/yaml"

    def __init__(
        self,
        *,
        test_url: str,
        test_interval: int,
        allow_lan: bool = False,
        listen_port: int = 7890,
        dns_nameserver: tuple[str, ...] = (
            "https://dns.alidns.com/dns-query",
            "https://doh.pub/dns-query",
        ),
        dns_fallback: tuple[str, ...] = (
            "https://1.1.1.1/dns-query",
            "https://dns.google/dns-query",
        ),
        dns_bootstrap: tuple[str, ...] = ("223.5.5.5", "119.29.29.29"),
        dns_fake_ip_range: str = "198.18.0.1/16",
        dns_ipv6: bool = False,
    ) -> None:
        self._test_url = test_url
        self._test_interval = test_interval
        self._allow_lan = allow_lan
        self._listen_port = listen_port
        self._dns_nameserver = tuple(dns_nameserver)
        self._dns_fallback = tuple(dns_fallback)
        self._dns_bootstrap = tuple(dns_bootstrap)
        self._dns_fake_ip_range = dns_fake_ip_range
        self._dns_ipv6 = dns_ipv6

    # ------------------------------------------------------------------ #
    def build_proxies(self, nodes: Iterable[ProxyNode]) -> list[dict[str, object]]:
        proxies: list[dict[str, object]] = []
        seen: set[str] = set()
        for node in nodes:
            rendered = node_to_mihomo(node)
            if not rendered:
                continue
            name = str(rendered["name"])
            if name in seen:  # Mihomo rejects duplicate proxy names
                idx = 2
                while f"{name}-{idx}" in seen:
                    idx += 1
                rendered["name"] = f"{name}-{idx}"
                name = f"{name}-{idx}"
            seen.add(name)
            proxies.append(rendered)
        return proxies

    def build_proxy_groups(self, proxy_names: list[str]) -> list[dict[str, object]]:
        if not proxy_names:
            return []
        return [
            {
                "name": "AUTO",
                "type": "url-test",
                "url": self._test_url,
                "interval": self._test_interval,
                "tolerance": 50,
                "proxies": list(proxy_names),
            },
            {
                "name": "SELECT",
                "type": "select",
                "proxies": ["AUTO", "DIRECT", *proxy_names],
            },
        ]

    @staticmethod
    def build_rules() -> list[str]:
        return ["MATCH,SELECT"]

    def build_dns(self) -> dict[str, object]:
        return {
            "enable": True,
            "ipv6": self._dns_ipv6,
            "default-nameserver": list(self._dns_bootstrap),
            "enhanced-mode": "fake-ip",
            "fake-ip-range": self._dns_fake_ip_range,
            "nameserver": list(self._dns_nameserver),
            "fallback": list(self._dns_fallback),
            "fallback-filter": {"geoip": True, "geoip-code": "CN"},
        }

    def render(self, nodes: Iterable[ProxyNode]) -> str:
        proxies = self.build_proxies(nodes)
        if not proxies:
            raise ConversionError("no renderable proxies after conversion")
        names = [str(p["name"]) for p in proxies]
        config: dict[str, object] = {
            "mixed-port": self._listen_port,
            "allow-lan": self._allow_lan,
            "mode": "rule",
            "log-level": "info",
            "unified-delay": True,
            "external-controller": "",
            "dns": self.build_dns(),
            "proxies": proxies,
            "proxy-groups": self.build_proxy_groups(names),
            "rules": self.build_rules(),
        }
        return _dump_yaml(config)


class _SafeDumper(yaml.SafeDumper):
    """Block-style, human-readable YAML output."""


def _str_presenter(dumper: _SafeDumper, data: str) -> yaml.Node:
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_SafeDumper.add_representer(str, _str_presenter)


def _dump_yaml(data: dict[str, object]) -> str:
    return yaml.dump(
        data,
        Dumper=_SafeDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=1000,
    )
