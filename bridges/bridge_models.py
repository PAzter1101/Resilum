"""Validated models for the supervisor's config families. One model per
``_spawn_*`` in bridge_spawn; the parsers in bridge_config feed untrusted YAML
entries into these via ``model_validate``."""

import ipaddress
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _host_port_ok(value: str) -> bool:
    host, sep, port = str(value).rpartition(":")
    return bool(sep and host and port.isdigit() and 0 < int(port) < 65536)


class _Bridge(BaseModel):
    mode: Literal["listen", "connect"]
    services: list[str]
    identity: str
    tcp: str
    target: str | None = None
    use_own: Literal["smart", "true", "false"] = "smart"
    allow_countries: list[str] = Field(default_factory=list)
    deny_countries: list[str] = Field(default_factory=list)
    probe_targets: list[str] = Field(default_factory=list)
    exit_country: str = "*"

    @field_validator("tcp")
    @classmethod
    def _valid_tcp(cls, v: str) -> str:
        if not _host_port_ok(v):
            raise ValueError("must be host:port")
        return v


class _Vpn(BaseModel):
    mode: Literal["server", "client"]
    identity: str
    tun: str | None = None
    subnet: str | None = None
    uplink: str | None = None
    mtu: int | None = Field(default=None, ge=68, le=65535)
    target: str | None = None

    @field_validator("subnet")
    @classmethod
    def _valid_subnet(cls, v):
        if v is not None:
            try:
                ipaddress.ip_network(v, strict=False)
            except ValueError:
                raise ValueError("must be valid CIDR")
        return v

    @property
    def extra_args(self) -> list[str]:
        out: list[str] = []
        for key in ("tun", "subnet", "uplink", "mtu", "target"):
            value = getattr(self, key)
            if value is not None:
                out += [f"--{key}", str(value)]
        return out


class _Covert(BaseModel):
    carrier: str
    role: Literal["server", "client", "both"] = "both"
    addresses: list[str] = Field(default_factory=list)
    interface: str = ""
    mtu: int = Field(default=1400, ge=68, le=65535)
    # RNS timeout-patience / interface-priority hint, not a data-rate cap
    bitrate: int = Field(default=32000, ge=1000, le=1_000_000_000)
    identity: str = ""

    @field_validator("addresses")
    @classmethod
    def _valid_addresses(cls, v: list[str]) -> list[str]:
        for addr in v:
            try:
                ipaddress.ip_address(addr)
            except ValueError:
                raise ValueError(f"{addr!r} is not a valid IP address")
        return v
