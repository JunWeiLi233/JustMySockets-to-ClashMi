"""Security and concurrency tests for durable subscription-link storage."""

from __future__ import annotations

import base64
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest
from subscription_converter.link_store import (
    CapacityReached,
    DuplicateSourceLimitReached,
    LinkStore,
    LinkStoreConfigurationError,
    LinkStoreCorruptionError,
    NetworkLimitReached,
    UserLimitReached,
)

__all__ = ()

TEST_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode()
OTHER_KEY = base64.urlsafe_b64encode(bytes(range(1, 33))).decode()
SOURCE = "https://jmssub.net/members/getsub.php?service=123&id=private-value"


def _store(
    path: Path,
    *,
    limit: int = 10,
    per_source: int = 3,
    per_user: int | None = None,
    per_network: int | None = None,
) -> LinkStore:
    return LinkStore(
        path,
        TEST_KEY,
        max_active_links=limit,
        max_links_per_source=per_source,
        max_links_per_user=per_user,
        max_links_per_network=per_network,
        clock=lambda: 1_700_000_000,
    )


def test_round_trip_persists_across_store_restart_without_plaintext(tmp_path: Path) -> None:
    database = tmp_path / "links.sqlite3"
    first = _store(database)
    created = first.create(SOURCE, "clash")

    assert SOURCE not in repr(created)
    assert created.access_token not in repr(created)
    assert created.manage_key not in repr(created)
    assert first.get(created.access_token) is not None

    second = _store(database)
    stored = second.get(created.access_token)
    assert stored is not None
    assert stored.source_url == SOURCE
    assert stored.format == "clash"
    assert stored.created_at == 1_700_000_000
    assert SOURCE not in repr(stored)

    persisted_bytes = b"".join(path.read_bytes() for path in tmp_path.iterdir() if path.is_file())
    assert SOURCE.encode() not in persisted_bytes
    assert created.access_token.encode() not in persisted_bytes
    assert created.manage_key.encode() not in persisted_bytes
    assert os.stat(database).st_mode & 0o777 == 0o600


def test_wrong_key_fails_closed_before_reading_records(tmp_path: Path) -> None:
    database = tmp_path / "links.sqlite3"
    _store(database).create(SOURCE, "clash")
    with pytest.raises(LinkStoreConfigurationError, match="does not match"):
        LinkStore(database, OTHER_KEY, max_active_links=10, max_links_per_source=3)


@pytest.mark.parametrize("secret", ["", "not-base64", base64.urlsafe_b64encode(b"short").decode()])
def test_invalid_secret_key_is_rejected(tmp_path: Path, secret: str) -> None:
    with pytest.raises(LinkStoreConfigurationError, match="LINK_SECRET_KEY"):
        LinkStore(
            tmp_path / "links.sqlite3",
            secret,
            max_active_links=10,
            max_links_per_source=3,
        )


def test_close_permanently_deletes_record_and_releases_capacity(tmp_path: Path) -> None:
    store = _store(tmp_path / "links.sqlite3", limit=1)
    created = store.create(SOURCE, "clash")
    assert not store.capacity().accepting

    closed = store.close(created.manage_key)
    assert closed is not None
    assert closed.source_url == SOURCE
    assert store.get(created.access_token) is None
    assert store.close(created.manage_key) is None
    assert store.capacity().accepting


def test_access_token_cannot_close_and_management_key_cannot_read(tmp_path: Path) -> None:
    store = _store(tmp_path / "links.sqlite3")
    created = store.create(SOURCE, "clash")
    assert store.close(created.access_token) is None
    assert store.get(created.manage_key) is None
    assert store.get(created.access_token) is not None


def test_invalid_token_shapes_do_not_touch_records(tmp_path: Path) -> None:
    store = _store(tmp_path / "links.sqlite3")
    created = store.create(SOURCE, "clash")
    assert store.get("../etc/passwd") is None
    assert store.close("x" * 10_000) is None
    assert store.get(created.access_token) is not None


def test_source_duplicate_limit_is_enforced_and_format_scoped(tmp_path: Path) -> None:
    store = _store(tmp_path / "links.sqlite3", per_source=1)
    store.create(SOURCE, "clash")
    with pytest.raises(DuplicateSourceLimitReached):
        store.create(SOURCE, "clash")
    store.create(SOURCE, "sing-box")


def test_capacity_check_and_insert_are_atomic_under_concurrency(tmp_path: Path) -> None:
    store = _store(tmp_path / "links.sqlite3", limit=2)

    def create(index: int) -> bool:
        try:
            store.create(f"https://jmssub.net/sub?id={index}", "clash")
        except CapacityReached:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create, range(8)))

    assert sum(results) == 2
    assert store.capacity().active == 2
    assert store.capacity().remaining == 0


def test_tampered_ciphertext_is_detected(tmp_path: Path) -> None:
    database = tmp_path / "links.sqlite3"
    store = _store(database)
    created = store.create(SOURCE, "clash")
    with closing(sqlite3.connect(database)) as connection:
        encrypted = connection.execute("SELECT encrypted_url FROM links").fetchone()[0]
        tampered = bytearray(encrypted)
        tampered[-1] ^= 1
        connection.execute("UPDATE links SET encrypted_url = ?", (bytes(tampered),))
        connection.commit()

    with pytest.raises(LinkStoreCorruptionError, match="authentication"):
        store.get(created.access_token)


def test_pseudonymous_user_and_network_quotas_are_independent(tmp_path: Path) -> None:
    store = _store(
        tmp_path / "links.sqlite3",
        per_source=10,
        per_user=1,
        per_network=2,
    )
    owner_a = "A" * 43
    owner_b = "B" * 43
    store.create(
        f"{SOURCE}&slot=1",
        "clash",
        owner_token=owner_a,
        network_identity="203.0.113.10",
    )
    with pytest.raises(UserLimitReached):
        store.create(
            f"{SOURCE}&slot=2",
            "clash",
            owner_token=owner_a,
            network_identity="203.0.113.11",
        )
    store.create(
        f"{SOURCE}&slot=3",
        "clash",
        owner_token=owner_b,
        network_identity="203.0.113.10",
    )
    with pytest.raises(NetworkLimitReached):
        store.create(
            f"{SOURCE}&slot=4",
            "clash",
            owner_token="C" * 43,
            network_identity="203.0.113.10",
        )


def test_identity_material_is_never_persisted_in_plaintext(tmp_path: Path) -> None:
    database = tmp_path / "links.sqlite3"
    owner = "Z" * 43
    network = "198.51.100.77"
    store = _store(database)
    store.create(SOURCE, "clash", owner_token=owner, network_identity=network)

    persisted = b"".join(path.read_bytes() for path in tmp_path.iterdir() if path.is_file())
    assert owner.encode() not in persisted
    assert network.encode() not in persisted


def test_admin_enrollment_is_single_device_bound_and_secret_minimising(tmp_path: Path) -> None:
    store = _store(tmp_path / "links.sqlite3")
    owner = "O" * 43
    device = "D" * 43
    created = store.create(
        SOURCE,
        "clash",
        owner_token=owner,
        network_identity="192.0.2.8",
    )

    assert store.enroll_admin_device(device, owner)
    assert not store.enroll_admin_device("E" * 43, "P" * 43)
    assert store.is_admin_device(device, owner)
    assert not store.is_admin_device(device, "P" * 43)
    restarted = _store(tmp_path / "links.sqlite3")
    assert restarted.is_admin_device(device, owner)
    overview = store.admin_overview()
    assert overview.active == 1
    assert overview.unique_users == 1
    assert overview.unique_networks == 1
    assert SOURCE not in repr(overview)
    assert created.access_token not in repr(overview)
    assert created.manage_key not in repr(overview)

    csrf = store.admin_csrf_token(device)
    assert store.verify_admin_csrf(device, csrf)
    assert not store.verify_admin_csrf(device, "X" * 43)
    assert store.admin_close(overview.links[0].link_ref) is not None
    assert store.capacity().active == 0


def test_schema_v1_is_upgraded_without_losing_existing_links(tmp_path: Path) -> None:
    database = tmp_path / "links.sqlite3"
    first = _store(database)
    created = first.create(SOURCE, "clash")
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("DROP TABLE admin_device")
        connection.execute("DROP TABLE link_ownership")
        connection.execute("UPDATE metadata SET value = ? WHERE key = 'schema_version'", (b"1",))
        connection.commit()

    upgraded = _store(database)
    assert upgraded.get(created.access_token) is not None
    assert upgraded.admin_overview().unidentified_links == 1
