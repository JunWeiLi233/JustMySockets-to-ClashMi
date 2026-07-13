"""Protocol parser implementations and the default registry.

Each protocol lives in its own module and implements the
:class:`~subscription_converter.parser_port.ProtocolParser` interface. The
default registry is assembled here without any global mutable state — callers
receive a fresh immutable :class:`ParserRegistry` via :func:`default_registry`.
"""

from __future__ import annotations

from subscription_converter.parser_port import ParserRegistry

from .hysteria2 import Hysteria2Parser
from .ss import ShadowsocksParser
from .trojan import TrojanParser
from .tuic import TuicParser
from .vless import VlessParser
from .vmess import VmessParser

__all__ = [
    "Hysteria2Parser",
    "ShadowsocksParser",
    "TrojanParser",
    "TuicParser",
    "VlessParser",
    "VmessParser",
    "default_registry",
]


def default_registry() -> ParserRegistry:
    """Return a fresh immutable registry with all built-in parsers registered.

    Both ``hysteria2`` and ``hy2`` scheme aliases are handled by accepting the
    alias at the orchestrator level (normalising ``hy2`` -> ``hysteria2``).
    """
    reg = (
        ParserRegistry.empty()
        .with_parser(ShadowsocksParser())
        .with_parser(VmessParser())
        .with_parser(VlessParser())
        .with_parser(TrojanParser())
        .with_parser(Hysteria2Parser())
        .with_parser(TuicParser())
    )
    return reg
