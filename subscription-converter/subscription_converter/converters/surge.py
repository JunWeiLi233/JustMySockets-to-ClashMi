"""Minimal Surge converter (placeholder).

Demonstrates the extensible pipeline: same parser, different renderer. Full
protocol coverage is a follow-up; only SS/VMess/Trojan are emitted here.
"""

from __future__ import annotations

from collections.abc import Iterable

from subscription_converter.converters import BaseConverter
from subscription_converter.models import ProxyNode, ProxyType

__all__ = ["SurgeConverter"]


class SurgeConverter(BaseConverter):
    name = "surge"
    media_type = "text/plain"

    def __init__(self, **_: object) -> None:
        # Accept and ignore the shared kwargs so the factory can build every
        # format uniformly.
        pass

    def render(self, nodes: Iterable[ProxyNode]) -> str:
        lines: list[str] = ["[General]", "dns-server = 223.5.5.5", "", "[Proxy]", "DIRECT = direct"]
        for node in nodes:
            if node.type == ProxyType.SS:
                lines.append(
                    f"{node.safe_name} = ss, {node.server}, {node.port}, "
                    f"encrypt-method={node.cipher}, password={node.password}"
                )
            elif node.type == ProxyType.VMESS:
                lines.append(
                    f"{node.safe_name} = vmess, {node.server}, {node.port}, username={node.uuid}"
                )
            elif node.type == ProxyType.TROJAN:
                lines.append(
                    f"{node.safe_name} = trojan, {node.server}, {node.port}, password={node.password}"
                )
        lines += ["", "[Proxy Group]", "SELECT = select, DIRECT", "", "[Rule]", "MATCH,SELECT"]
        return "\n".join(lines) + "\n"
