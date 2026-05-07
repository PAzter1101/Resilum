"""Connect-side announce handlers.

Each service in the fallback chain registers a persistent handler
that updates the shared ``targets`` dict on every fresh announce —
and tears down the live Link to a peer that becomes incompatible (or
otherwise stops parsing) so the pump notices and frees its TCP half."""

import RNS

from .. import announce_payload
from ..constants import DEFAULT_ASPECTS
from ..identity import load_or_create_identity
from .link_registry import _teardown_links_for


def _hash_from_identity_file(identity_path: str, aspects: list) -> bytes | None:
    """Return the destination hash that a listen-bridge with the given
    identity file would announce on the given aspects, without
    registering anything with Transport. Used by the connect-bridge to
    skip its own listen-bridge during auto-discovery."""
    try:
        identity = load_or_create_identity(identity_path)
    except Exception as exc:
        RNS.log(
            f"[bridge:connect] could not load skip-self identity "
            f"{identity_path}: {exc}",
            RNS.LOG_WARNING,
        )
        return None
    sibling = RNS.Destination(
        identity, RNS.Destination.OUT, RNS.Destination.SINGLE, *aspects
    )
    h: bytes = sibling.hash
    return h


def _make_announce_handler(
    service: str, aspects: list, skip_hashes: set, targets: dict, lock
):
    """Persistent announce handler — stays registered for the bridge's
    whole lifetime, refreshing the target hash each time the service's
    listen-side re-announces (or a fresh peer joins)."""
    aspect_filter = ".".join(aspects)

    class _Handler:
        def __init__(self):
            self.aspect_filter = aspect_filter
            self.receive_path_responses = False

        def received_announce(self, destination_hash, announced_identity, app_data):
            del announced_identity
            if destination_hash in skip_hashes:
                RNS.log(
                    f"[bridge:connect/{service}] ignoring self-announce "
                    f"{RNS.prettyhexrep(destination_hash)}",
                    RNS.LOG_DEBUG,
                )
                return
            if announce_payload.parse(app_data) is None:
                _teardown_links_for(
                    destination_hash, reason="incompatible or malformed announce"
                )
                with lock:
                    targets.pop(service, None)
                return
            with lock:
                previous = targets.get(service)
                targets[service] = destination_hash
            if previous != destination_hash:
                RNS.log(
                    f"[bridge:connect/{service}] target now "
                    f"{RNS.prettyhexrep(destination_hash)}",
                    RNS.LOG_INFO,
                )

    return _Handler()


def _build_skip_hashes(skip_self_paths, services):
    """Per-service skip-self set: each listen-bridge identity is
    interpreted with each service's aspect to derive the destination
    hash that node's listen-bridge would announce. Skip every
    combination so own-announces never end up as a target."""
    skips: dict = {service: set() for service in services}
    for path in skip_self_paths or []:
        for service in services:
            aspects = DEFAULT_ASPECTS + [service]
            h = _hash_from_identity_file(path, aspects)
            if h is not None:
                skips[service].add(h)
                RNS.log(
                    f"[bridge:connect/{service}] will skip self-announce "
                    f"{RNS.prettyhexrep(h)} (from {path})",
                    RNS.LOG_VERBOSE,
                )
    return skips
