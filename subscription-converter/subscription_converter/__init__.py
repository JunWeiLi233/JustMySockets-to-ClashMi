"""subscription-converter package.

Public domain models and parser contract. Concrete protocol parsers,
converters, and the FastAPI application are introduced in subsequent pull
requests.
"""

from __future__ import annotations

from subscription_converter.models import (
    ProxyNode,
    ProxyType,
    Subscription,
    TlsOptions,
    TransportOptions,
)

__version__ = "0.1.0"

__all__ = [
    "ProxyNode",
    "ProxyType",
    "Subscription",
    "TlsOptions",
    "TransportOptions",
    "__version__",
]
