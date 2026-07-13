"""Converter registry and factory.

Maps a format name to a converter class. Adding a new output format means
subclassing :class:`~subscription_converter.converters.BaseConverter`, adding it
here, and (optionally) wiring a route — the parser and models are untouched.
"""

from __future__ import annotations

from typing import Any

from subscription_converter.converters import BaseConverter, ConversionError
from subscription_converter.converters.mihomo import MihomoConverter
from subscription_converter.converters.singbox import SingBoxConverter
from subscription_converter.converters.surge import SurgeConverter

__all__ = ["CONVERTERS", "get_converter"]

CONVERTERS: dict[str, type[BaseConverter]] = {
    "clash": MihomoConverter,
    "mihomo": MihomoConverter,
    "surge": SurgeConverter,
    "sing-box": SingBoxConverter,
}


def get_converter(name: str, **kwargs: Any) -> BaseConverter:
    cls = CONVERTERS.get(name.lower())
    if cls is None:
        raise ConversionError(f"unknown output format: {name}")
    return cls(**kwargs)
