"""Connect-side announce handlers backed by CandidateRegistry."""

import RNS

from .. import announce_payload
from ..constants import DEFAULT_ASPECTS
from ..identity import load_or_create_identity
from .link_registry import _teardown_links_for


def _hash_from_identity_file(identity_path: str, aspects: list) -> bytes | None:
    """Return the destination hash for a given identity + aspects, without
    registering with Transport. Used to compute skip-self hashes."""
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


def _make_registry_handler(service, aspects, skip_hashes, registry):
    """Announce handler that upserts discovered peers into CandidateRegistry,
    skips own hashes, and removes peers whose announce stops parsing."""
    aspect_filter = ".".join(aspects)

    class _Handler:
        def __init__(self):
            self.aspect_filter = aspect_filter
            self.receive_path_responses = False

        def received_announce(self, destination_hash, announced_identity, app_data):
            del announced_identity
            if destination_hash in skip_hashes:
                return
            parsed = announce_payload.parse(app_data)
            if parsed is None:
                _teardown_links_for(destination_hash, reason="incompatible announce")
                registry.remove(service, destination_hash)
                return
            registry.upsert(
                service,
                destination_hash,
                exit_country=parsed.exit_country,
                capabilities=parsed.capabilities,
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
