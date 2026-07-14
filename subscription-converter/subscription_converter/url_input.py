r"""Forgiving subscription-URL input handling.

Real users paste subscription URLs in ways that break a strict parser:

1. **Stray backslashes** inserted by some shells (`https://x\?service\=1\&id=2`)
   — the backslashes must be stripped before parsing.
2. **Leading/trailing whitespace** — including a literal `%20` from a botched
   copy-paste into a `curl` command.
3. **Already percent-encoded URLs** — a user who encoded the URL themselves and
   then pasted it after `?url=` (so it arrives *double-encoded* in the raw query
   string) needs to be detected and decoded once.
4. **Unencoded query separators** — `?`, `&`, `=` in the pasted URL arrive as
   separate query params when FastAPI splits the query string. We recover them
   from the raw query string.

This module exposes :func:`normalize_subscription_url` which takes whatever the
HTTP layer received and returns the clean, un-encoded upstream URL the parser
should fetch. It never logs the URL or its credentials.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

__all__ = ["InvalidSubscriptionURL", "normalize_subscription_url"]


class InvalidSubscriptionURL(ValueError):
    """Raised when the input cannot be turned into a usable URL."""


# Matches a leading backslash immediately before URL-significant punctuation
# that shells sometimes escape: ? = & / : #
_BACKSLASH_BEFORE_PUNCT = re.compile(r"\\(?=[?=/&:#])")


def normalize_subscription_url(raw: str) -> str:
    """Return a clean, un-encoded URL from messy user input.

    Args:
        raw: Whatever arrived in the ``url`` query parameter (possibly after
            manual percent-encoding, with stray backslashes, or extra spaces).

    Returns:
        The canonical URL to fetch (``https://host/path?query``).

    Raises:
        InvalidSubscriptionURL: if no ``http(s)://`` host can be recovered.
    """
    if raw is None:
        raise InvalidSubscriptionURL("missing 'url' query parameter")

    text = raw.strip()
    # A literal "%20" at the start is the residue of `curl %20https...`.
    while text.startswith("%20"):
        text = text[3:].lstrip()
    if not text:
        raise InvalidSubscriptionURL("missing 'url' query parameter")

    # Strip stray backslashes that shells insert before ? = & / : #
    text = _BACKSLASH_BEFORE_PUNCT.sub("", text)

    # Detect and undo a single layer of percent-encoding if the user
    # pre-encoded the URL themselves (e.g. pasted `https%3A%2F%2F...`). We only
    # decode when it actually looks like an encoded URL *and* decoding reveals an
    # http(s):// scheme; otherwise we leave it untouched.
    decoded = _maybe_decode_once(text)
    if decoded is not None:
        text = decoded

    # Reject anything that is still not an http(s) URL.
    lowered = text.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        raise InvalidSubscriptionURL(
            "url must start with http:// or https:// (after normalisation)"
        )

    parsed = urlsplit(text)
    if not parsed.netloc:
        raise InvalidSubscriptionURL("url must include a host")

    # URL fragments are browser-local and are never sent to an upstream HTTP
    # server. Dropping them prevents equivalent subscriptions from bypassing
    # duplicate-source and cache limits by varying an irrelevant suffix.
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def _maybe_decode_once(text: str) -> str | None:
    """If ``text`` is a percent-encoded URL, decode it once and return the result.

    Returns ``None`` if ``text`` does not look percent-encoded.
    """
    from urllib.parse import unquote

    # Heuristic: contains encoded scheme separator or path separator.
    looks_encoded = (
        ("https%3a" in text.lower())
        or ("http%3a" in text.lower())
        or ("%2f" in text.lower() and "%3a" in text.lower())
    )
    if not looks_encoded:
        return None
    try:
        decoded = unquote(text)
    except Exception:  # pragma: no cover - defensive
        return None
    # Only trust the decode if it produced an http(s) scheme; otherwise the
    # input wasn't an encoded URL after all.
    if decoded.lower().startswith(("http://", "https://")):
        return decoded
    return None
