"""Tests for the parser contract (port) and registry."""

from __future__ import annotations

import pytest
from subscription_converter.models import ProxyNode, ProxyType
from subscription_converter.parser_port import (
    ParserError,
    ParserRegistry,
    RegistryError,
)

__all__ = ()


class _FakeSsParser:
    """A minimal concrete parser implementing the ProtocolParser protocol."""

    @property
    def scheme(self) -> str:
        return "ss"

    def parse(self, uri: str) -> ProxyNode:
        if not uri.startswith("ss://"):
            raise ParserError("not an ss uri")
        return ProxyNode(
            type=ProxyType.SS,
            name="fake",
            server="h",
            port=1,
            cipher="aes-256-gcm",
            password="p",
        )


class _FakeVmessParser:
    @property
    def scheme(self) -> str:
        return "vmess"

    def parse(self, uri: str) -> ProxyNode:
        return ProxyNode(
            type=ProxyType.VMESS,
            name="fake-vmess",
            server="h",
            port=1,
            uuid="u",
        )


def test_registry_starts_empty() -> None:
    reg = ParserRegistry.empty()
    assert len(reg) == 0
    assert reg.schemes() == ()


def test_registry_with_parser_is_immutable() -> None:
    reg = ParserRegistry.empty()
    new = reg.with_parser(_FakeSsParser())
    # original unchanged
    assert len(reg) == 0
    assert len(new) == 1
    assert "ss" in new


def test_registry_get_returns_parser() -> None:
    reg = ParserRegistry.empty().with_parser(_FakeSsParser())
    parser = reg.get("ss")
    assert parser is not None
    assert parser.scheme == "ss"


def test_registry_get_case_insensitive() -> None:
    reg = ParserRegistry.empty().with_parser(_FakeSsParser())
    assert reg.get("SS") is not None


def test_registry_get_unknown_returns_none() -> None:
    reg = ParserRegistry.empty()
    assert reg.get("ss") is None


def test_registry_rejects_duplicate_scheme() -> None:
    reg = ParserRegistry.empty().with_parser(_FakeSsParser())
    with pytest.raises(RegistryError):
        reg.with_parser(_FakeSsParser())


def test_registry_schemes_sorted() -> None:
    reg = ParserRegistry.empty().with_parser(_FakeVmessParser()).with_parser(_FakeSsParser())
    assert reg.schemes() == ("ss", "vmess")


def test_protocol_parser_is_structural() -> None:
    """Objects with the right shape satisfy ProtocolParser without inheriting."""
    from subscription_converter.parser_port import ProtocolParser

    assert isinstance(_FakeSsParser(), ProtocolParser)


def test_fake_parser_actually_parses() -> None:
    """Sanity: the test double returns a valid node."""
    parser = _FakeSsParser()
    node = parser.parse("ss://anything")
    assert node.type is ProxyType.SS
    assert node.server == "h"


def test_fake_parser_raises_on_bad_uri() -> None:
    parser = _FakeSsParser()
    with pytest.raises(ParserError):
        parser.parse("vmess://nope")
