"""Minimal sing-box converter (placeholder).

Demonstrates the extensible pipeline. Emits a selector over SS outbounds only;
full protocol coverage is a follow-up.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from subscription_converter.converters import BaseConverter, ConversionError
from subscription_converter.models import ProxyNode, ProxyType

__all__ = ["SingBoxConverter"]


class SingBoxConverter(BaseConverter):
    name = "sing-box"
    media_type = "application/json"

    def __init__(self, **_: object) -> None:
        pass

    def render(self, nodes: Iterable[ProxyNode]) -> str:
        outbounds: list[dict[str, object]] = [{"type": "direct", "tag": "direct"}]
        tags: list[str] = ["direct"]
        emitted = 0
        for node in nodes:
            if node.type != ProxyType.SS:
                continue
            outbounds.append(
                {
                    "type": "shadowsocks",
                    "tag": node.safe_name,
                    "server": node.server,
                    "server_port": node.port,
                    "method": node.cipher or "",
                    "password": node.password or "",
                }
            )
            tags.append(node.safe_name)
            emitted += 1
        if emitted == 0:
            raise ConversionError("no renderable proxies after conversion")
        selector = {"type": "selector", "tag": "SELECT", "outbounds": tags}
        config: dict[str, object] = {
            "log": {"level": "info"},
            "outbounds": [*outbounds, selector],
            "route": {"final": "SELECT"},
        }
        return json.dumps(config, indent=2)
