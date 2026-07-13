"""TUIC (``tuic://``) parser."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from subscription_converter.models import ProxyNode, ProxyType, TlsOptions
from subscription_converter.parser_port import ParserError

from ._helpers import parse_bool, parse_qs_flat

__all__ = ["TuicParser"]


class TuicParser:
    """Parses ``tuic://`` URIs (v5)."""

    @property
    def scheme(self) -> str:
        return "tuic"

    def parse(self, uri: str) -> ProxyNode:
        if not uri.startswith("tuic://"):
            raise ParserError("not a tuic uri")
        parsed = urlparse(uri)
        if not parsed.hostname or not parsed.port:
            raise ParserError("tuic missing host/port")
        qs = parse_qs_flat(parsed.query)
        uuid = unquote(parsed.username or "")
        password = unquote(parsed.password) if parsed.password else None
        return ProxyNode(
            type=ProxyType.TUIC,
            name=unquote(parsed.fragment) or f"tuic-{parsed.hostname}-{parsed.port}",
            server=parsed.hostname,
            port=parsed.port,
            uuid=uuid,
            password=password,
            congestion_controller=qs.get("congestion_control") or None,
            udp_relay_mode=qs.get("udp_relay_mode") or None,
            tls=TlsOptions(
                enabled=True,
                sni=qs.get("sni") or parsed.hostname,
                alpn=qs.get("alpn", "").split(",") if qs.get("alpn") else [],
                skip_cert_verify=parse_bool(qs.get("allow_insecure")),
            ),
        )
