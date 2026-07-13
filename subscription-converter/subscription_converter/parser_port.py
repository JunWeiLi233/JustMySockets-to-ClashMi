"""Parser contract (port) and scheme registry.

This module defines the interface every concrete protocol parser must satisfy,
plus a registry mapping URI schemes to parsers. Keeping the contract in its own
module lets the parser package depend on the *interface* rather than concrete
implementations — the parser orchestrator (PR-3) wires real parsers in.

Design rationale
----------------
- ``ProtocolParser`` is a ``typing.Protocol`` (structural typing): concrete
  parsers need not inherit, they just need to provide ``scheme`` and ``parse``.
- ``ParserRegistry`` is a small immutable container so registries can be
  composed and replaced (e.g. in tests) without mutating global state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from subscription_converter.models import ProxyNode

__all__ = ["ParserError", "ParserRegistry", "ProtocolParser", "RegistryError"]


class ParserError(ValueError):
    """Raised when a single URI cannot be parsed into a node."""


class RegistryError(ValueError):
    """Raised on invalid registry operations (duplicate scheme, etc.)."""


@runtime_checkable
class ProtocolParser(Protocol):
    """Structural interface for a per-scheme URI parser.

    Implementations parse a single URI (e.g. ``ss://...``) and return a
    :class:`~subscription_converter.models.ProxyNode`, or raise
    :class:`ParserError` if the URI is malformed.
    """

    @property
    def scheme(self) -> str:  # pragma: no cover - protocol signature
        """The lowercased URI scheme this parser handles, without ``://``."""
        ...

    def parse(self, uri: str) -> ProxyNode:  # pragma: no cover - protocol signature
        """Parse ``uri`` into a :class:`ProxyNode`.

        Raises:
            ParserError: if the URI is malformed or unsupported.
        """
        ...


@dataclass(frozen=True)
class ParserRegistry:
    """Immutable mapping of URI scheme -> parser.

    Instances are created with :meth:`with_parser` so the registry is built up
    without mutation; the orchestrator assembles a final registry at startup.
    """

    _parsers: dict[str, ProtocolParser]

    @classmethod
    def empty(cls) -> ParserRegistry:
        return cls(_parsers={})

    def with_parser(self, parser: ProtocolParser) -> ParserRegistry:
        """Return a new registry with ``parser`` registered under its scheme."""
        scheme = parser.scheme.lower()
        if scheme in self._parsers:
            raise RegistryError(f"scheme already registered: {scheme}")
        new_map = dict(self._parsers)
        new_map[scheme] = parser
        return ParserRegistry(_parsers=new_map)

    def get(self, scheme: str) -> ProtocolParser | None:
        return self._parsers.get(scheme.lower())

    def schemes(self) -> tuple[str, ...]:
        return tuple(sorted(self._parsers))

    def __len__(self) -> int:
        return len(self._parsers)

    def __contains__(self, scheme: object) -> bool:
        return isinstance(scheme, str) and scheme.lower() in self._parsers
