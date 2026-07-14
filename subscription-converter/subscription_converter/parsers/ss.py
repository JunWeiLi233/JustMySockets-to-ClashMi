"""Shadowsocks (``ss://``) parser — SIP002 and legacy forms."""

from __future__ import annotations

from urllib.parse import unquote

from subscription_converter.models import ProxyNode, ProxyType
from subscription_converter.parser_port import ParserError

from ._helpers import b64decode_loose, parse_qs_flat

__all__ = ["ShadowsocksParser"]


def _normalise_plugin_name(raw: str | None) -> str | None:
    """Map simple-obfs names to the canonical Mihomo name ``obfs``."""
    if not raw:
        return None
    r = raw.strip().lower()
    if r in {"obfs-local", "simple-obfs", "obfs"}:
        return "obfs"
    return r or None


def _safe_port(raw: str) -> int:
    """Parse a port, raising ``ParserError`` (not ValueError) on bad input."""
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise ParserError(f"ss port not an integer: {raw!r}") from exc


class ShadowsocksParser:
    """Parses ``ss://`` URIs (SIP002 and legacy base64-wrapped forms)."""

    @property
    def scheme(self) -> str:
        return "ss"

    def parse(self, uri: str) -> ProxyNode:
        if not uri.startswith("ss://"):
            raise ParserError("not an ss uri")
        body = uri[len("ss://") :]
        name: str | None = None
        if "#" in body:
            body, frag = body.split("#", 1)
            name = unquote(frag)

        # SIP002: base64userinfo@host:port/?plugin=...
        if "@" in body:
            return self._parse_sip002(body, name)
        # legacy: base64(method:pass@host:port)
        return self._parse_legacy(body, name)

    def _parse_sip002(self, body: str, name: str | None) -> ProxyNode:
        userinfo, hostpart = body.rsplit("@", 1)
        # userinfo may itself be base64-encoded
        try:
            decoded = b64decode_loose(userinfo).decode("utf-8")
            if ":" in decoded:
                userinfo = decoded
        except (ValueError, UnicodeDecodeError):
            pass
        if ":" not in userinfo:
            raise ParserError("ss userinfo missing cipher:password")
        cipher, password = userinfo.split(":", 1)

        query = ""
        if "/" in hostpart:
            hostport, rest = hostpart.split("/", 1)
            query = rest.split("?", 1)[1] if "?" in rest else rest
        else:
            hostport = hostpart
        server, _, port_s = hostport.rpartition(":")
        if not server or not port_s:
            raise ParserError("ss host:port malformed")
        qs = parse_qs_flat(query)
        plugin_raw = qs.get("plugin")
        plugin_opts: str | None = None
        if plugin_raw:
            parts = plugin_raw.split(";")
            plugin_raw = parts[0]
            opts = {
                k.strip(): v.strip() for k, v in (p.split("=", 1) for p in parts[1:] if "=" in p)
            }
            plugin_opts = ";".join(f"{k}={v}" for k, v in opts.items())

        return ProxyNode(
            type=ProxyType.SS,
            name=name or f"ss-{server}-{port_s}",
            server=server,
            port=_safe_port(port_s),
            cipher=cipher,
            password=unquote(password),
            plugin=_normalise_plugin_name(plugin_raw),
            plugin_opts=plugin_opts,
        )

    def _parse_legacy(self, body: str, name: str | None) -> ProxyNode:
        try:
            decoded = b64decode_loose(body).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ParserError("ss legacy body not base64-decodable") from exc
        if "@" not in decoded:
            raise ParserError("ss legacy body missing @host:port")
        userinfo, hostport = decoded.rsplit("@", 1)
        if ":" not in userinfo:
            raise ParserError("ss legacy userinfo missing cipher:password")
        cipher, password = userinfo.split(":", 1)
        server, _, port_s = hostport.rpartition(":")
        if not server or not port_s:
            raise ParserError("ss legacy host:port malformed")
        return ProxyNode(
            type=ProxyType.SS,
            name=name or f"ss-{server}-{port_s}",
            server=server,
            port=_safe_port(port_s),
            cipher=cipher,
            password=unquote(password),
        )
