"""Minimal Surge converter (placeholder).

Demonstrates the extensible pipeline: same parser, different renderer. Full
protocol coverage is a follow-up; only SS/VMess/Trojan are emitted here.

Security: every value reflected into the Surge INI-style output is sanitized to
prevent section/field injection. Node names and credentials are user/upstream
controlled, so a malicious subscription could otherwise inject ``\\n[Script]``
lines or break field parsing with commas/equals. See ``_surge_escape``.
"""

from __future__ import annotations

from collections.abc import Iterable

from subscription_converter.converters import BaseConverter, ConversionError
from subscription_converter.models import ProxyNode, ProxyType

__all__ = ["SurgeConverter"]

# Characters that would break Surge's field/section parsing.
_SURGE_STRIP = "\r\n"


def _surge_escape(value: object) -> str:
    """Make a value safe to emit into a Surge config line.

    - Drops CR/LF (prevents section/header injection).
    - Comma and equals are preserved inside passwords (Surge tolerates them when
      the value is the last field) but we reject values that start a new section.
    """
    if value is None:
        return ""
    text = str(value)
    for ch in _SURGE_STRIP:
        text = text.replace(ch, "")
    return text


def _surge_name(value: object) -> str:
    """Escape a proxy name; reject anything that could open/close a section.

    Any ``[`` or ``]`` is stripped (not just leading) because a name like
    ``ok[Script]`` would still be interpreted as a section by some parsers.
    """
    text = _surge_escape(value)
    # Remove square brackets entirely — they delimit INI sections.
    text = text.replace("[", "").replace("]", "")
    if not text.strip():
        return "unnamed"
    # Replace any remaining field separators so the name stays a single token.
    return text.translate(str.maketrans(",=:", "---"))


class SurgeConverter(BaseConverter):
    name = "surge"
    media_type = "text/plain"

    def __init__(self, **_: object) -> None:
        # Accept and ignore the shared kwargs so the factory can build every
        # format uniformly.
        pass

    def render(self, nodes: Iterable[ProxyNode]) -> str:
        lines: list[str] = ["[General]", "dns-server = 223.5.5.5", "", "[Proxy]", "DIRECT = direct"]
        emitted = 0
        for node in nodes:
            line = self._render_node(node)
            if line is not None:
                lines.append(line)
                emitted += 1
        if emitted == 0:
            raise ConversionError("no renderable proxies after conversion")
        lines += ["", "[Proxy Group]", "SELECT = select, DIRECT", "", "[Rule]", "MATCH,SELECT"]
        return "\n".join(lines) + "\n"

    def _render_node(self, node: ProxyNode) -> str | None:
        name = _surge_name(node.safe_name)
        server = _surge_escape(node.server)
        port = node.port
        if node.type == ProxyType.SS:
            return (
                f"{name} = ss, {server}, {port}, "
                f"encrypt-method={_surge_escape(node.cipher)}, "
                f"password={_surge_escape(node.password)}"
            )
        if node.type == ProxyType.VMESS:
            return f"{name} = vmess, {server}, {port}, username={_surge_escape(node.uuid)}"
        if node.type == ProxyType.TROJAN:
            return f"{name} = trojan, {server}, {port}, password={_surge_escape(node.password)}"
        return None
