"""Guard against accidentally committing a real JMS bearer credential again."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

__all__ = ()

_JMS_CREDENTIAL = re.compile(
    r"jmssub\.net/members/getsub\.php\?service=(?P<service>\d+)&id=(?P<id>[0-9a-f-]+)",
    re.IGNORECASE,
)
_ALLOWED_FIXTURES = {
    ("123456", "00000000"),
    ("123456", "00000000-0000-4000-8000-000000000000"),
}


def test_source_tree_contains_only_the_documented_dummy_jms_credential() -> None:
    root = Path(__file__).parents[2]
    candidates = [root / "README.md"]
    candidates.extend((root / "subscription-converter").rglob("*.py"))

    findings: list[str] = []
    for path in candidates:
        if path == Path(__file__):
            continue
        text = unquote(path.read_text(encoding="utf-8"))
        for match in _JMS_CREDENTIAL.finditer(text):
            credential = (match.group("service"), match.group("id").lower())
            if credential not in _ALLOWED_FIXTURES:
                findings.append(str(path.relative_to(root)))

    assert not findings, f"real-looking JMS credentials found in: {sorted(set(findings))}"
