"""Hysteria2 (``hysteria2://`` / ``hy2://``) parser."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from subscription_converter.models import ProxyNode, ProxyType, TlsOptions
from subscription_converter.parser_port import ParserError

from ._helpers import parse_bool, parse_qs_flat

__all__ = ["Hysteria2Parser"]


class Hysteria2Parser:
    """Parses ``hysteria2://`` and ``hy2://`` URIs."""

    @property
    def scheme(self) -> str:
        return "hysteria2"

    def parse(self, uri: str) -> ProxyNode:
        if not (uri.startswith("hysteria2://") or uri.startswith("hy2://")):
            raise ParserError("not a hysteria2 uri")
        parsed = urlparse(uri)
        if not parsed.hostname or not parsed.port:
            raise ParserError("hysteria2 missing host/port")
        password = unquote(parsed.username or "")
        if parsed.password:
            password = unquote(parsed.password)
        qs = parse_qs_flat(parsed.query)
        return ProxyNode(
            type=ProxyType.HYSTERIA2,
            name=unquote(parsed.fragment) or f"hy2-{parsed.hostname}-{parsed.port}",
            server=parsed.hostname,
            port=parsed.port,
            password=password or None,
            obfs=qs.get("obfs") or None,
            obfs_password=qs.get("obfs-password") or None,
            up=qs.get("up") or None,
            down=qs.get("down") or None,
            tls=TlsOptions(
                enabled=True,
                sni=qs.get("sni") or parsed.hostname,
                alpn=qs.get("alpn", "").split(",") if qs.get("alpn") else ["h3"],
                skip_cert_verify=parse_bool(qs.get("insecure")),
                fingerprint=qs.get("fp") or None,
            ),
        )
