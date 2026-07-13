"""Converter registry and factory.

Maps a format name to a converter class. Adding a new output format means
subclassing :class:`~subscription_converter.converters.BaseConverter`, adding it
here, and (optionally) wiring a route — the parser and models are untouched.
"""

from __future__ import annotations

from typing import Any

from subscription_converter.converters import BaseConverter, ConversionError
from subscription_converter.converters.mihomo import MihomoConverter

__all__ = ["CONVERTERS", "get_converter"]

CONVERTERS: dict[str, type[BaseConverter]] = {
    "clash": MihomoConverter,
    "mihomo": MihomoConverter,
}


def get_converter(name: str, **kwargs: Any) -> BaseConverter:
    cls = CONVERTERS.get(name.lower())
    if cls is None:
        raise ConversionError(f"unknown output format: {name}")
    return cls(**kwargs)
