"""Provider-independent proxy domain models.

These Pydantic models form the intermediate representation between the parser
(which turns subscription URIs into :class:`ProxyNode` instances) and the
converters (which turn nodes into a target output format). Keeping them
decoupled from both input providers and output formats is what makes the
architecture extensible.

Design notes
------------
- All models are Pydantic v2 ``BaseModel`` subclasses with ``model_config =
  extra="ignore"`` so that unknown fields encountered in real-world
  subscriptions do not cause validation failures (forward compatibility).
- No model stores raw credentials in a way that would leak via ``repr``:
  sensitive fields are not specially tagged here, but log masking is enforced
  at the HTTP layer; models themselves are plain data carriers.
- Frozen models are avoided so that parsers can normalise/populate derived
  fields after construction; immutability is enforced by convention, not type.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "ProxyNode",
    "ProxyType",
    "Subscription",
    "TlsOptions",
    "TransportOptions",
]


class ProxyType(str, Enum):
    """Supported proxy protocols (normalised, lowercase)."""

    SS = "ss"
    SSR = "ssr"
    VMESS = "vmess"
    VLESS = "vless"
    TROJAN = "trojan"
    HYSTERIA2 = "hysteria2"
    HYSTERIA = "hysteria"
    TUIC = "tuic"
    UNKNOWN = "unknown"


class TlsOptions(BaseModel):
    """TLS-related options shared by several protocols."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    sni: str | None = None
    alpn: list[str] = Field(default_factory=list)
    skip_cert_verify: bool = False
    fingerprint: str | None = None  # uTLS fingerprint, e.g. "chrome"
    reality_public_key: str | None = None
    reality_short_id: str | None = None


class TransportOptions(BaseModel):
    """Layer-4 transport: tcp, ws, grpc, h2."""

    model_config = ConfigDict(extra="ignore")

    network: str = "tcp"  # tcp | ws | grpc | h2 | quic
    path: str | None = None
    host: str | None = None  # ws Host header / grpc authority
    grpc_service_name: str | None = None


class ProxyNode(BaseModel):
    """Normalised, provider-independent representation of a single proxy.

    Every output renderer reads from this object so adding a new output format
    never requires touching the parser.
    """

    model_config = ConfigDict(extra="ignore")

    type: ProxyType
    name: str
    server: str
    port: int = Field(ge=1, le=65535)

    # credentials / params
    password: str | None = None
    uuid: str | None = None
    cipher: str | None = None  # ss / vmess
    alter_id: int = 0  # vmess

    # ss simple-obfs / v2ray-plugin
    plugin: str | None = None
    plugin_opts: str | None = None

    tls: TlsOptions = Field(default_factory=TlsOptions)
    transport: TransportOptions = Field(default_factory=TransportOptions)

    flow: str | None = None  # vless xtls-rprx-vision

    # hysteria2 / hysteria
    obfs: str | None = None
    obfs_password: str | None = None
    up: str | None = None
    down: str | None = None

    # tuic
    congestion_controller: str | None = None
    udp_relay_mode: str | None = None

    # ssr
    ssr_obfs: str | None = None
    ssr_protocol: str | None = None
    ssr_protocol_param: str | None = None

    # generic
    udp: bool = True

    @field_validator("server")
    @classmethod
    def _server_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("server must be a non-empty hostname or address")
        return v.strip()

    @field_validator("name", mode="before")
    @classmethod
    def _default_name(cls, v: object) -> object:
        # Allow callers to omit the name; a placeholder is filled in by the
        # parser using server/port. A bare empty string is treated as missing.
        if v is None or (isinstance(v, str) and not v.strip()):
            return ""
        return v

    @property
    def safe_name(self) -> str:
        """Return a name safe for use as a YAML key / display string."""
        n = (self.name or "").strip()
        return n or f"{self.type.value}-{self.server}-{self.port}"


class Subscription(BaseModel):
    """A parsed subscription: the decoded nodes plus safe upstream metadata.

    ``fetched_at_iso`` is a UTC wall-clock timestamp of when the upstream was
    downloaded; it is safe to expose to clients. Upstream headers are filtered
    to an allow-list of non-sensitive metadata (see the parser).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    nodes: tuple[ProxyNode, ...]
    fetched_at_iso: str = ""
    upstream_headers: dict[str, str] = Field(default_factory=dict)

    @property
    def profile_update_interval(self) -> int | None:
        """Provider-suggested poll interval in hours, if the upstream sent one."""
        raw = self.upstream_headers.get("profile-update-interval")
        if not raw:
            return None
        try:
            return int(str(raw).strip())
        except ValueError:
            return None

    @property
    def subscription_userinfo(self) -> str:
        """Upstream traffic-quota header value, if present."""
        return self.upstream_headers.get("subscription-userinfo", "")
