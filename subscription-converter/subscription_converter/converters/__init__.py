"""Output converters.

Each converter turns a list of :class:`~subscription_converter.models.ProxyNode`
into a target format. The :data:`CONVERTERS` registry maps a format name to a
converter class so the HTTP layer can dispatch generically and new formats
(surge / sing-box) can be added without touching the parser.
"""

from __future__ import annotations

import abc
from collections.abc import Iterable

from subscription_converter.models import ProxyNode

__all__ = ["BaseConverter", "ConversionError"]


class ConversionError(ValueError):
    """Raised when rendering nodes into a target format fails."""


class BaseConverter(abc.ABC):
    """Abstract base. Subclasses render a node list into a target format."""

    name: str = "base"
    media_type: str = "text/plain"

    @abc.abstractmethod
    def render(self, nodes: Iterable[ProxyNode]) -> str:
        """Return the full configuration document as a string."""
        raise NotImplementedError
