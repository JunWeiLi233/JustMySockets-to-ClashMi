"""Shared decoding helpers for protocol parsers.

These helpers are deliberately free of any protocol-specific logic so they can
be reused across every concrete parser. Nothing here performs I/O.
"""

from __future__ import annotations

import base64
import binascii
from urllib.parse import parse_qs

__all__ = ["b64decode_loose", "looks_like_base64", "parse_bool", "parse_qs_flat"]


def b64decode_loose(data: str) -> bytes:
    """Decode base64, tolerating missing padding and urlsafe alphabets.

    Subscription payloads frequently omit padding and may use the URL-safe
    alphabet; this helper restores padding and normalises before decoding.
    """
    cleaned = data.strip().replace("\n", "").replace("\r", "").replace(" ", "")
    cleaned = cleaned.replace("-", "+").replace("_", "/")
    pad = (-len(cleaned)) % 4
    cleaned += "=" * pad
    try:
        return base64.b64decode(cleaned)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"invalid base64: {exc}") from exc


def parse_qs_flat(query: str) -> dict[str, str]:
    """Flatten ``parse_qs`` to a ``{key: first_value}`` mapping."""
    return {k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items() if v}


def parse_bool(value: str | None) -> bool:
    """Interpret common truthy strings (1/true/tls/yes) as ``True``."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "tls", "yes", "on"}


def looks_like_base64(payload: str) -> bool:
    """Heuristic: payload has no ``://`` and base64-decodes to text."""
    text = payload.strip()
    if not text or "://" in text.split()[0]:
        return False
    try:
        decoded = b64decode_loose(text)
    except ValueError:
        return False
    try:
        decoded.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return b"://" in decoded
