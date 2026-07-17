"""Announce payload encoding.

Every announce a Resilum bridge emits carries a small JSON envelope
identifying the running release (so peers can drop us when their
``major`` doesn't match — see :mod:`.version`) and, for discovery
plugins, the transport endpoint they would otherwise have put in
``app_data`` raw.

Wire format::

    {"v": "0.5.2", "ep": "<utf-8 endpoint>"}

``ep`` is omitted by transport-bridges (yggdrasil/socks-egress) that
have no peer-specific endpoint to advertise. Discovery plugins
(tor/i2p) embed their hostname there as ASCII.
"""

import json
from dataclasses import dataclass
from typing import Optional

import RNS

from .version import VERSION, is_compatible


@dataclass
class ParsedAnnounce:
    version: str
    endpoint: Optional[bytes]
    exit_country: str = "*"
    capabilities: tuple = ()


def pack(
    endpoint: Optional[bytes] = None,
    exit_country: str = "*",
    capabilities: tuple = (),
) -> bytes:
    payload: dict = {"v": VERSION}
    if endpoint is not None:
        payload["ep"] = endpoint.decode("utf-8")
    if exit_country and exit_country != "*":
        payload["co"] = exit_country
    if capabilities:
        payload["cap"] = list(capabilities)
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def parse(raw: Optional[bytes]) -> Optional[ParsedAnnounce]:
    """Decode an inbound announce. Returns ``None`` (≡ "drop this
    peer") for missing, malformed, or version-incompatible payloads;
    the reason is logged at WARNING for incompatibility, DEBUG for
    parse failures (those are common when a stranger announces on the
    same aspect with their own format)."""
    if not raw:
        return None
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        RNS.log(f"[announce_payload] not JSON: {exc}", RNS.LOG_DEBUG)
        return None
    if not isinstance(decoded, dict):
        return None
    peer_version = decoded.get("v")
    if not isinstance(peer_version, str):
        return None
    if not is_compatible(peer_version):
        RNS.log(
            f"[announce_payload] peer on {peer_version!r} is incompatible "
            f"with local {VERSION!r}, dropping",
            RNS.LOG_WARNING,
        )
        return None
    endpoint_str = decoded.get("ep")
    endpoint = endpoint_str.encode("utf-8") if isinstance(endpoint_str, str) else None
    country = decoded.get("co")
    exit_country = country if isinstance(country, str) and country else "*"
    caps = decoded.get("cap")
    capabilities = (
        tuple(c for c in caps if isinstance(c, str)) if isinstance(caps, list) else ()
    )
    return ParsedAnnounce(
        version=peer_version,
        endpoint=endpoint,
        exit_country=exit_country,
        capabilities=capabilities,
    )
