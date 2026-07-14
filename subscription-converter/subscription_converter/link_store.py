"""Encrypted durable storage for revocable subscription links.

The store deliberately has no HTTP-framework dependency.  It persists only:

* keyed digests of the public access token and private management key;
* a keyed digest of the upstream URL + output format for abuse limiting; and
* keyed digests of pseudonymous device/network/admin identities; and
* the upstream URL encrypted with AES-256-GCM.

Plaintext upstream URLs, bearer tokens, and client IP addresses are never
written to disk. Capacity checks and inserts share one ``BEGIN IMMEDIATE``
transaction, so concurrent creators cannot exceed the configured limits.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import os
import re
import secrets
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

__all__ = [
    "AdminLinkRecord",
    "AdminOverview",
    "CapacityReached",
    "ClosedLink",
    "CreatedLink",
    "DuplicateSourceLimitReached",
    "LinkStore",
    "LinkStoreConfigurationError",
    "LinkStoreCorruptionError",
    "NetworkLimitReached",
    "StoreCapacity",
    "StoredLink",
    "UserLimitReached",
]

_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]{43}$")
_FORMATS: Final[frozenset[str]] = frozenset({"clash", "sing-box", "surge"})
_SCHEMA_VERSION: Final[bytes] = b"2"
_KEY_CHECK_CONTEXT: Final[bytes] = b"jms-link-store:key-check:v1"
_ACCESS_CONTEXT: Final[bytes] = b"jms-link-store:access:v1\x00"
_MANAGE_CONTEXT: Final[bytes] = b"jms-link-store:manage:v1\x00"
_SOURCE_CONTEXT: Final[bytes] = b"jms-link-store:source:v1\x00"
_OWNER_CONTEXT: Final[bytes] = b"jms-link-store:owner:v1\x00"
_NETWORK_CONTEXT: Final[bytes] = b"jms-link-store:network:v1\x00"
_ADMIN_DEVICE_CONTEXT: Final[bytes] = b"jms-link-store:admin-device:v1\x00"
_ADMIN_CSRF_CONTEXT: Final[bytes] = b"jms-link-store:admin-csrf:v1\x00"
_ENCRYPTION_CONTEXT: Final[bytes] = b"jms-link-store:encryption-key:v1"
_DIGEST_CONTEXT: Final[bytes] = b"jms-link-store:digest-key:v1"
_AAD_PREFIX: Final[bytes] = b"jms-link-store:url:v1\x00"


class LinkStoreConfigurationError(RuntimeError):
    """The durable store cannot be opened safely with its current settings."""


class LinkStoreCorruptionError(RuntimeError):
    """A stored ciphertext failed authenticated decryption."""


class CapacityReached(RuntimeError):
    """The configured active-link limit has been reached."""


class DuplicateSourceLimitReached(RuntimeError):
    """One upstream subscription already owns its allowed number of links."""


class UserLimitReached(RuntimeError):
    """One pseudonymous browser device has reached its active-link limit."""


class NetworkLimitReached(RuntimeError):
    """One pseudonymous network has reached its active-link limit."""


@dataclass(frozen=True)
class CreatedLink:
    """Secrets returned exactly once when a durable link is created."""

    access_token: str = field(repr=False)
    manage_key: str = field(repr=False)
    created_at: int


@dataclass(frozen=True)
class StoredLink:
    """Decrypted record used by the conversion layer."""

    source_url: str = field(repr=False)
    format: str
    created_at: int


@dataclass(frozen=True)
class ClosedLink:
    """Minimal close result; the URL is used only to purge the memory cache."""

    source_url: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class StoreCapacity:
    active: int
    limit: int

    @property
    def remaining(self) -> int:
        return max(self.limit - self.active, 0)

    @property
    def accepting(self) -> bool:
        return self.active < self.limit


@dataclass(frozen=True)
class AdminLinkRecord:
    """Non-secret link metadata shown to the enrolled admin device."""

    link_ref: str
    user_ref: str
    network_ref: str
    format: str
    created_at: int


@dataclass(frozen=True)
class AdminOverview:
    """Aggregate, privacy-preserving registry metadata for the admin UI."""

    active: int
    limit: int
    unique_users: int
    unique_networks: int
    unidentified_links: int
    links: tuple[AdminLinkRecord, ...]


class LinkStore:
    """SQLite-backed encrypted registry for non-expiring, revocable links."""

    def __init__(
        self,
        database_path: str | Path,
        secret_key: str,
        *,
        max_active_links: int,
        max_links_per_source: int,
        max_links_per_user: int | None = None,
        max_links_per_network: int | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if max_active_links <= 0:
            raise LinkStoreConfigurationError("MAX_ACTIVE_LINKS must be positive")
        if max_links_per_source <= 0:
            raise LinkStoreConfigurationError("MAX_LINKS_PER_SOURCE must be positive")
        if max_links_per_user is not None and max_links_per_user <= 0:
            raise LinkStoreConfigurationError("MAX_LINKS_PER_USER must be positive")
        if max_links_per_network is not None and max_links_per_network <= 0:
            raise LinkStoreConfigurationError("MAX_LINKS_PER_NETWORK must be positive")

        self._database_path = Path(database_path)
        self._max_active_links = max_active_links
        self._max_links_per_source = max_links_per_source
        self._max_links_per_user = max_links_per_user or max_active_links
        self._max_links_per_network = max_links_per_network or max_active_links
        self._clock = clock

        master_key = self._decode_secret_key(secret_key)
        self._encryption_key = hmac.digest(master_key, _ENCRYPTION_CONTEXT, "sha256")
        self._digest_key = hmac.digest(master_key, _DIGEST_CONTEXT, "sha256")
        self._aead = AESGCM(self._encryption_key)
        self._initialise_database()

    @staticmethod
    def _decode_secret_key(value: str) -> bytes:
        raw = value.strip()
        if not raw:
            raise LinkStoreConfigurationError("LINK_SECRET_KEY is required")
        try:
            decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        except (binascii.Error, ValueError) as exc:
            raise LinkStoreConfigurationError(
                "LINK_SECRET_KEY must be URL-safe base64 for exactly 32 bytes"
            ) from exc
        if len(decoded) != 32:
            raise LinkStoreConfigurationError(
                "LINK_SECRET_KEY must be URL-safe base64 for exactly 32 bytes"
            )
        return decoded

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path,
            timeout=5.0,
            isolation_level=None,
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
        except sqlite3.Error:
            connection.close()
            raise
        return connection

    def _initialise_database(self) -> None:
        try:
            self._database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with closing(self._connect()) as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value BLOB NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS links (
                        access_digest BLOB PRIMARY KEY,
                        manage_digest BLOB NOT NULL UNIQUE,
                        source_digest BLOB NOT NULL,
                        encrypted_url BLOB NOT NULL,
                        format TEXT NOT NULL CHECK (format IN ('clash', 'sing-box', 'surge')),
                        created_at INTEGER NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS links_source_digest_idx
                    ON links (source_digest);

                    CREATE TABLE IF NOT EXISTS link_ownership (
                        access_digest BLOB PRIMARY KEY
                            REFERENCES links(access_digest) ON DELETE CASCADE,
                        owner_digest BLOB NOT NULL,
                        network_digest BLOB NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS link_ownership_owner_idx
                    ON link_ownership (owner_digest);

                    CREATE INDEX IF NOT EXISTS link_ownership_network_idx
                    ON link_ownership (network_digest);

                    CREATE TABLE IF NOT EXISTS admin_device (
                        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                        device_digest BLOB NOT NULL UNIQUE,
                        owner_digest BLOB NOT NULL,
                        created_at INTEGER NOT NULL
                    );
                    """
                )
                version_row = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'schema_version'"
                ).fetchone()
                if version_row is None:
                    connection.execute(
                        "INSERT INTO metadata(key, value) VALUES('schema_version', ?)",
                        (_SCHEMA_VERSION,),
                    )
                elif bytes(version_row["value"]) == b"1":
                    connection.execute(
                        "UPDATE metadata SET value = ? WHERE key = 'schema_version'",
                        (_SCHEMA_VERSION,),
                    )
                key_check = hmac.digest(self._digest_key, _KEY_CHECK_CONTEXT, "sha256")
                connection.execute(
                    "INSERT OR IGNORE INTO metadata(key, value) VALUES('key_check', ?)",
                    (key_check,),
                )
                version_row = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'schema_version'"
                ).fetchone()
                key_row = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'key_check'"
                ).fetchone()
        except (OSError, sqlite3.Error) as exc:
            raise LinkStoreConfigurationError("persistent link database is not writable") from exc

        if version_row is None or bytes(version_row["value"]) != _SCHEMA_VERSION:
            raise LinkStoreConfigurationError("unsupported persistent link database schema")
        if key_row is None or not hmac.compare_digest(bytes(key_row["value"]), key_check):
            raise LinkStoreConfigurationError(
                "LINK_SECRET_KEY does not match the persistent link database"
            )
        try:
            os.chmod(self._database_path, 0o600)
        except OSError as exc:
            raise LinkStoreConfigurationError(
                "cannot secure persistent link database permissions"
            ) from exc

    def _digest(self, context: bytes, value: str) -> bytes:
        return hmac.digest(self._digest_key, context + value.encode("utf-8"), "sha256")

    def _source_digest(self, source_url: str, fmt: str) -> bytes:
        material = f"{fmt}\x00{source_url}".encode()
        return hmac.digest(self._digest_key, _SOURCE_CONTEXT + material, "sha256")

    def _identity_digest(self, context: bytes, value: str) -> bytes:
        return hmac.digest(self._digest_key, context + value.encode("utf-8"), "sha256")

    @staticmethod
    def _encode_digest(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode_digest(value: str) -> bytes | None:
        if not _TOKEN_RE.fullmatch(value):
            return None
        try:
            decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        except (binascii.Error, ValueError):
            return None
        return decoded if len(decoded) == 32 else None

    def identity_key(self, owner_token: str, network_identity: str) -> str:
        """Return a non-reversible, process-safe key for rate-limit buckets."""
        owner = self._identity_digest(_OWNER_CONTEXT, owner_token)
        network = self._identity_digest(_NETWORK_CONTEXT, network_identity)
        return self._encode_digest(hmac.digest(self._digest_key, owner + network, "sha256"))

    @staticmethod
    def _valid_token(value: str) -> bool:
        return _TOKEN_RE.fullmatch(value) is not None

    def _encrypt_url(self, source_url: str, access_digest: bytes) -> bytes:
        nonce = os.urandom(12)
        encrypted = self._aead.encrypt(
            nonce,
            source_url.encode("utf-8"),
            _AAD_PREFIX + access_digest,
        )
        return nonce + encrypted

    def _decrypt_url(self, encrypted: bytes, access_digest: bytes) -> str:
        if len(encrypted) < 29:  # 12-byte nonce + >=1 byte plaintext + 16-byte tag
            raise LinkStoreCorruptionError("stored subscription ciphertext is invalid")
        try:
            plaintext = self._aead.decrypt(
                encrypted[:12],
                encrypted[12:],
                _AAD_PREFIX + access_digest,
            )
            return plaintext.decode("utf-8")
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise LinkStoreCorruptionError(
                "stored subscription ciphertext failed authentication"
            ) from exc

    def capacity(self) -> StoreCapacity:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM links").fetchone()
        active = int(row["count"]) if row is not None else 0
        return StoreCapacity(active=active, limit=self._max_active_links)

    def create(
        self,
        source_url: str,
        fmt: str,
        *,
        owner_token: str | None = None,
        network_identity: str | None = None,
    ) -> CreatedLink:
        """Atomically enforce limits and create a new durable link."""
        if fmt not in _FORMATS:
            raise ValueError("unsupported output format")

        source_digest = self._source_digest(source_url, fmt)
        owner_digest = (
            self._identity_digest(_OWNER_CONTEXT, owner_token) if owner_token is not None else None
        )
        network_digest = (
            self._identity_digest(_NETWORK_CONTEXT, network_identity)
            if network_identity is not None
            else None
        )
        if (owner_digest is None) != (network_digest is None):
            raise ValueError("owner_token and network_identity must be provided together")
        for _ in range(3):  # collisions are cryptographically implausible; retry defensively.
            access_token = secrets.token_urlsafe(32)
            manage_key = secrets.token_urlsafe(32)
            access_digest = self._digest(_ACCESS_CONTEXT, access_token)
            manage_digest = self._digest(_MANAGE_CONTEXT, manage_key)
            encrypted_url = self._encrypt_url(source_url, access_digest)
            created_at = int(self._clock())

            with closing(self._connect()) as connection:
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    count_row = connection.execute("SELECT COUNT(*) AS count FROM links").fetchone()
                    active = int(count_row["count"]) if count_row is not None else 0
                    if active >= self._max_active_links:
                        connection.rollback()
                        raise CapacityReached("active subscription capacity reached")

                    source_row = connection.execute(
                        "SELECT COUNT(*) AS count FROM links WHERE source_digest = ?",
                        (source_digest,),
                    ).fetchone()
                    source_count = int(source_row["count"]) if source_row is not None else 0
                    if source_count >= self._max_links_per_source:
                        connection.rollback()
                        raise DuplicateSourceLimitReached(
                            "this upstream subscription already has the maximum number of links"
                        )

                    if owner_digest is not None and network_digest is not None:
                        owner_row = connection.execute(
                            "SELECT COUNT(*) AS count FROM link_ownership WHERE owner_digest = ?",
                            (owner_digest,),
                        ).fetchone()
                        owner_count = int(owner_row["count"]) if owner_row is not None else 0
                        if owner_count >= self._max_links_per_user:
                            connection.rollback()
                            raise UserLimitReached("browser-device link limit reached")

                        network_row = connection.execute(
                            "SELECT COUNT(*) AS count FROM link_ownership WHERE network_digest = ?",
                            (network_digest,),
                        ).fetchone()
                        network_count = int(network_row["count"]) if network_row is not None else 0
                        if network_count >= self._max_links_per_network:
                            connection.rollback()
                            raise NetworkLimitReached("network link limit reached")

                    connection.execute(
                        """
                        INSERT INTO links(
                            access_digest,
                            manage_digest,
                            source_digest,
                            encrypted_url,
                            format,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            access_digest,
                            manage_digest,
                            source_digest,
                            encrypted_url,
                            fmt,
                            created_at,
                        ),
                    )
                    if owner_digest is not None and network_digest is not None:
                        connection.execute(
                            """
                            INSERT INTO link_ownership(
                                access_digest,
                                owner_digest,
                                network_digest
                            ) VALUES (?, ?, ?)
                            """,
                            (access_digest, owner_digest, network_digest),
                        )
                    connection.commit()
                except sqlite3.IntegrityError:
                    connection.rollback()
                    continue
            return CreatedLink(
                access_token=access_token,
                manage_key=manage_key,
                created_at=created_at,
            )

        raise RuntimeError("could not allocate a unique subscription token")

    def get(self, access_token: str) -> StoredLink | None:
        if not self._valid_token(access_token):
            return None
        access_digest = self._digest(_ACCESS_CONTEXT, access_token)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT encrypted_url, format, created_at
                FROM links
                WHERE access_digest = ?
                """,
                (access_digest,),
            ).fetchone()
        if row is None:
            return None
        source_url = self._decrypt_url(bytes(row["encrypted_url"]), access_digest)
        return StoredLink(
            source_url=source_url,
            format=str(row["format"]),
            created_at=int(row["created_at"]),
        )

    def close(self, manage_key: str) -> ClosedLink | None:
        """Permanently delete one link using its independent management key."""
        if not self._valid_token(manage_key):
            return None
        manage_digest = self._digest(_MANAGE_CONTEXT, manage_key)
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT access_digest, encrypted_url
                    FROM links
                    WHERE manage_digest = ?
                    """,
                    (manage_digest,),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return None
                connection.execute(
                    "DELETE FROM links WHERE manage_digest = ?",
                    (manage_digest,),
                )
                connection.commit()
            except sqlite3.Error:
                connection.rollback()
                raise

        try:
            source_url = self._decrypt_url(
                bytes(row["encrypted_url"]),
                bytes(row["access_digest"]),
            )
        except LinkStoreCorruptionError:
            source_url = None
        return ClosedLink(source_url=source_url)

    def admin_enrolled(self) -> bool:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT 1 FROM admin_device WHERE singleton = 1").fetchone()
        return row is not None

    def enroll_admin_device(self, device_token: str, owner_token: str) -> bool:
        """Atomically enroll the first and only browser-profile admin credential."""
        if not self._valid_token(device_token) or not self._valid_token(owner_token):
            raise ValueError("invalid device credential")
        device_digest = self._identity_digest(_ADMIN_DEVICE_CONTEXT, device_token)
        owner_digest = self._identity_digest(_OWNER_CONTEXT, owner_token)
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                exists = connection.execute(
                    "SELECT 1 FROM admin_device WHERE singleton = 1"
                ).fetchone()
                if exists is not None:
                    connection.rollback()
                    return False
                connection.execute(
                    """
                    INSERT INTO admin_device(singleton, device_digest, owner_digest, created_at)
                    VALUES (1, ?, ?, ?)
                    """,
                    (device_digest, owner_digest, int(self._clock())),
                )
                connection.commit()
            except sqlite3.Error:
                connection.rollback()
                raise
        return True

    def is_admin_device(self, device_token: str, owner_token: str) -> bool:
        if not self._valid_token(device_token) or not self._valid_token(owner_token):
            return False
        device_digest = self._identity_digest(_ADMIN_DEVICE_CONTEXT, device_token)
        owner_digest = self._identity_digest(_OWNER_CONTEXT, owner_token)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT 1 FROM admin_device
                WHERE singleton = 1 AND device_digest = ? AND owner_digest = ?
                """,
                (device_digest, owner_digest),
            ).fetchone()
        return row is not None

    def admin_csrf_token(self, device_token: str) -> str:
        if not self._valid_token(device_token):
            raise ValueError("invalid device credential")
        digest = self._identity_digest(_ADMIN_CSRF_CONTEXT, device_token)
        return self._encode_digest(digest)

    def verify_admin_csrf(self, device_token: str, csrf_token: str) -> bool:
        if not self._valid_token(csrf_token):
            return False
        try:
            expected = self.admin_csrf_token(device_token)
        except ValueError:
            return False
        return hmac.compare_digest(expected, csrf_token)

    def admin_overview(self, *, limit: int = 100) -> AdminOverview:
        safe_limit = min(max(limit, 1), 500)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    links.access_digest,
                    links.format,
                    links.created_at,
                    link_ownership.owner_digest,
                    link_ownership.network_digest
                FROM links
                LEFT JOIN link_ownership USING(access_digest)
                ORDER BY links.created_at DESC, links.access_digest
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
            aggregate = connection.execute(
                """
                SELECT
                    COUNT(*) AS active,
                    COUNT(DISTINCT link_ownership.owner_digest) AS unique_users,
                    COUNT(DISTINCT link_ownership.network_digest) AS unique_networks,
                    SUM(CASE WHEN link_ownership.access_digest IS NULL THEN 1 ELSE 0 END)
                        AS unidentified
                FROM links
                LEFT JOIN link_ownership USING(access_digest)
                """
            ).fetchone()
        records = tuple(
            AdminLinkRecord(
                link_ref=self._encode_digest(bytes(row["access_digest"])),
                user_ref=(
                    self._encode_digest(bytes(row["owner_digest"]))[:12]
                    if row["owner_digest"] is not None
                    else "pre-identity"
                ),
                network_ref=(
                    self._encode_digest(bytes(row["network_digest"]))[:12]
                    if row["network_digest"] is not None
                    else "pre-identity"
                ),
                format=str(row["format"]),
                created_at=int(row["created_at"]),
            )
            for row in rows
        )
        return AdminOverview(
            active=int(aggregate["active"]) if aggregate is not None else 0,
            limit=self._max_active_links,
            unique_users=int(aggregate["unique_users"]) if aggregate is not None else 0,
            unique_networks=int(aggregate["unique_networks"]) if aggregate is not None else 0,
            unidentified_links=int(aggregate["unidentified"] or 0) if aggregate is not None else 0,
            links=records,
        )

    def admin_close(self, link_ref: str) -> ClosedLink | None:
        """Close a link by its non-bearer admin reference."""
        access_digest = self._decode_digest(link_ref)
        if access_digest is None:
            return None
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT encrypted_url FROM links WHERE access_digest = ?",
                    (access_digest,),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return None
                connection.execute(
                    "DELETE FROM links WHERE access_digest = ?",
                    (access_digest,),
                )
                connection.commit()
            except sqlite3.Error:
                connection.rollback()
                raise
        try:
            source_url = self._decrypt_url(bytes(row["encrypted_url"]), access_digest)
        except LinkStoreCorruptionError:
            source_url = None
        return ClosedLink(source_url=source_url)
