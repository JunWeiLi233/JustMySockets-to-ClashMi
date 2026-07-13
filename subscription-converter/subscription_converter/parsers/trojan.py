"""Trojan (``trojan://``) parser — ws/grpc aware."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from subscription_converter.models import ProxyNode, ProxyType, TlsOptions, TransportOptions
from subscription_converter.parser_port import ParserError

from ._helpers import parse_bool, parse_qs_flat

__all__ = ["TrojanParser"]


class TrojanParser:
    """Parses ``trojan://`` URIs."""

    @property
    def scheme(self) -> str:
        return "trojan"

    def parse(self, uri: str) -> ProxyNode:
        if not uri.startswith("trojan://"):
            raise ParserError("not a trojan uri")
        parsed = urlparse(uri)
        if not parsed.hostname or not parsed.port:
            raise ParserError("trojan missing host/port")
        password = unquote(parsed.username or "")
        if not password:
            raise ParserError("trojan missing password")
        qs = parse_qs_flat(parsed.query)
        net = (qs.get("type") or "tcp").lower()
        sni = qs.get("sni") or parsed.hostname
        return ProxyNode(
            type=ProxyType.TROJAN,
            name=unquote(parsed.fragment) or f"trojan-{parsed.hostname}-{parsed.port}",
            server=parsed.hostname,
            port=parsed.port,
            password=password,
            tls=TlsOptions(
                enabled=True,
                sni=sni,
                alpn=qs.get("alpn", "").split(",") if qs.get("alpn") else [],
                fingerprint=qs.get("fp") or None,
                skip_cert_verify=parse_bool(qs.get("allowInsecure")),
            ),
            transport=TransportOptions(
                network=net,
                path=qs.get("path"),
                host=qs.get("host"),
                grpc_service_name=qs.get("serviceName") if net == "grpc" else None,
            ),
        )
