"""VLESS (``vless://``) parser — REALITY + ws/grpc aware."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from subscription_converter.models import ProxyNode, ProxyType, TlsOptions, TransportOptions
from subscription_converter.parser_port import ParserError

from ._helpers import parse_bool, parse_qs_flat

__all__ = ["VlessParser"]


class VlessParser:
    """Parses ``vless://`` URIs including REALITY transports."""

    @property
    def scheme(self) -> str:
        return "vless"

    def parse(self, uri: str) -> ProxyNode:
        if not uri.startswith("vless://"):
            raise ParserError("not a vless uri")
        parsed = urlparse(uri)
        if not parsed.hostname or not parsed.port:
            raise ParserError("vless missing host/port")
        uuid = unquote(parsed.username or "")
        if not uuid:
            raise ParserError("vless missing uuid")
        qs = parse_qs_flat(parsed.query)
        net = (qs.get("type") or "tcp").lower()
        security = qs.get("security", "none")
        tls_enabled = security != "none"
        tls = TlsOptions(
            enabled=tls_enabled,
            sni=qs.get("sni") or None,
            alpn=qs.get("alpn", "").split(",") if qs.get("alpn") else [],
            fingerprint=qs.get("fp") or None,
            reality_public_key=qs.get("pbk") or None,
            reality_short_id=qs.get("sid") or None,
            skip_cert_verify=parse_bool(qs.get("allowInsecure")),
        )
        transport = TransportOptions(
            network=net,
            path=qs.get("path"),
            host=qs.get("host") or qs.get("headerType"),
            grpc_service_name=qs.get("serviceName") if net == "grpc" else None,
        )
        return ProxyNode(
            type=ProxyType.VLESS,
            name=unquote(parsed.fragment) or f"vless-{parsed.hostname}-{parsed.port}",
            server=parsed.hostname,
            port=parsed.port,
            uuid=uuid,
            flow=qs.get("flow") or None,
            tls=tls,
            transport=transport,
        )
