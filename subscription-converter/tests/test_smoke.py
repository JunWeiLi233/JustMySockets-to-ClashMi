"""Smoke test: the package is importable and reports its version.

This is the minimal guard that the scaffolding (pyproject.toml, package layout,
pytest/pythonpath config) is wired up correctly. It will be augmented by real
domain tests in subsequent PRs.
"""

from __future__ import annotations

import subscription_converter


def test_package_importable() -> None:
    assert hasattr(subscription_converter, "__version__")


def test_version_is_pep440_shaped() -> None:
    version = subscription_converter.__version__
    # cheap sanity check: dotted numeric version
    parts = version.split(".")
    assert len(parts) >= 2, f"unexpected version: {version!r}"
    assert all(p[0].isdigit() for p in parts), f"non-numeric version segment: {version!r}"
