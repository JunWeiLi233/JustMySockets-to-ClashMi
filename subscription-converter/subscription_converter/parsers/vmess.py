"""VMess (``vmess://``) parser — v2rayN JSON form."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from subscription_converter.models import ProxyNode, ProxyType, TlsOptions, TransportOptions
from subscription_converter.parser_port import ParserError

from ._helpers import b64decode_loose, parse_bool

__all__ = ["VmessParser"]


class VmessParser:
    """Parses ``vmess://`` links encoded as v2rayN JSON (base64-wrapped)."""

    @property
    def scheme(self) -> str:
        return "vmess"

    def parse(self, uri: str) -> ProxyNode:
        if not uri.startswith("vmess://"):
            raise ParserError("not a vmess uri")
        try:
            payload = b64decode_loose(uri[len("vmess://") :]).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ParserError("vmess body not base64-decodable") from exc
        try:
            cfg = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ParserError("vmess body is not valid JSON") from exc
        if not isinstance(cfg, Mapping):
            raise ParserError("vmess JSON must be an object")

        server = str(cfg.get("add", "")).strip()
        port_raw = cfg.get("port", 0)
        try:
            port = int(port_raw)
        except (TypeError, ValueError) as exc:
            raise ParserError(f"vmess port invalid: {port_raw!r}") from exc
        if not server or not port:
            raise ParserError("vmess missing server/port")

        alpn_raw = cfg.get("alpn")
        tls = TlsOptions(
            enabled=parse_bool(str(cfg.get("tls", ""))),
            sni=cfg.get("sni") or cfg.get("peer") or None,
            alpn=str(alpn_raw).split(",") if alpn_raw else [],
            fingerprint=cfg.get("fp") or None,
        )
        net = str(cfg.get("net", "tcp")).lower()
        transport = TransportOptions(
            network=net,
            path=cfg.get("path"),
            host=cfg.get("host"),
            grpc_service_name=cfg.get("path") if net == "grpc" else None,
        )
        return ProxyNode(
            type=ProxyType.VMESS,
            name=str(cfg.get("ps") or f"vmess-{server}-{port}"),
            server=server,
            port=port,
            uuid=str(cfg.get("id", "")),
            alter_id=_as_int(cfg.get("aid", 0)),
            cipher=str(cfg.get("scy", "auto")),
            tls=tls,
            transport=transport,
        )


def _as_int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0
