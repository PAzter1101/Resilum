"""Connect mode: listen on a local TCP port and tunnel each connection
through an RNS Link to a known anchor identity.

Supports a priority list of services so a single TCP endpoint can
fall through transports — e.g. try ``socks-egress`` first (direct
public-IP exit), fall back to ``tor`` (Tor SOCKS via mesh) if the
direct egress is unreachable. Both the discovery half (announce
handlers) and the dispatch half (per-connection target picker) honour
the order in which services were given on the command line."""

import socket
import sys
import threading
import time

import RNS

from . import announce_payload
from .constants import DEFAULT_ASPECTS, LINK_ESTABLISH_TIMEOUT, PATH_REQUEST_TIMEOUT
from .identity import load_or_create_identity
from .pump import wire_link_to_socket

TARGET_DISCOVERY_TIMEOUT = 90


def _resolve_target(target_hash, aspects):
    """Return an OUT-direction destination for ``target_hash``, kicking
    off a path-request and waiting up to ``PATH_REQUEST_TIMEOUT``."""
    if not RNS.Transport.has_path(target_hash):
        RNS.Transport.request_path(target_hash)
        deadline = time.time() + PATH_REQUEST_TIMEOUT
        while time.time() < deadline and not RNS.Transport.has_path(target_hash):
            time.sleep(0.1)

    if not RNS.Transport.has_path(target_hash):
        return None

    remote_identity = RNS.Identity.recall(target_hash)
    if remote_identity is None:
        return None

    return RNS.Destination(
        remote_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        *aspects,
    )


def _open_link(target_dest, target_hash):
    link = RNS.Link(target_dest)
    deadline = time.time() + LINK_ESTABLISH_TIMEOUT
    while time.time() < deadline and link.status != RNS.Link.ACTIVE:
        time.sleep(0.1)
    if link.status != RNS.Link.ACTIVE:
        RNS.log(
            f"[bridge:connect] Link to {RNS.prettyhexrep(target_hash)} "
            f"did not become active in {LINK_ESTABLISH_TIMEOUT}s",
            RNS.LOG_WARNING,
        )
        link.teardown()
        return None
    return link


def _try_one_service(sock, service: str, target_hash: bytes, aspects: list) -> bool:
    """Attempt to dispatch ``sock`` through one service's target. Returns
    True if the Link is up and the pump is wired (caller must NOT close
    the socket)."""
    RNS.log(
        f"[bridge:connect/{service}] resolving target "
        f"{RNS.prettyhexrep(target_hash)}",
        RNS.LOG_VERBOSE,
    )
    target_dest = _resolve_target(target_hash, aspects)
    if target_dest is None:
        RNS.log(
            f"[bridge:connect/{service}] no path to "
            f"{RNS.prettyhexrep(target_hash)} after {PATH_REQUEST_TIMEOUT}s",
            RNS.LOG_WARNING,
        )
        return False

    link = _open_link(target_dest, target_hash)
    if link is None:
        return False

    RNS.log(
        f"[bridge:connect/{service}] Link active, wiring TCP",
        RNS.LOG_VERBOSE,
    )
    wire_link_to_socket(link, sock, label=f"connect/{service}")
    return True


def _handle_outbound(sock, services: list, targets, lock):
    """Try each service in priority order. On the first one that yields
    a working Link, hand the socket off to the pump and return. If all
    services fail, close the socket."""
    for service in services:
        with lock:
            target_hash = targets.get(service)
        if target_hash is None:
            RNS.log(
                f"[bridge:connect/{service}] no target known yet, skipping",
                RNS.LOG_DEBUG,
            )
            continue
        aspects = DEFAULT_ASPECTS + [service]
        if _try_one_service(sock, service, target_hash, aspects):
            return
    RNS.log(
        "[bridge:connect] no service in fallback chain yielded a Link, "
        "dropping TCP connection",
        RNS.LOG_WARNING,
    )
    sock.close()


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
                # Already logged inside parse() at the appropriate level
                # — drop the peer as either malformed or version-mismatched.
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
    hash that node's listen-bridge would announce. We skip every
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


def _wait_for_any_target(targets, lock, services, timeout):
    """Block until at least one of the services in ``services`` has a
    target hash in the shared dict, or the timeout elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with lock:
            if any(targets.get(s) is not None for s in services):
                return True
        time.sleep(0.5)
    return False


def run(args):
    load_or_create_identity(args.identity)
    services = list(args.service) if args.service else ["generic"]

    targets: dict = {}
    lock = threading.Lock()

    if args.target:
        # Legacy single-target mode: --target overrides discovery for
        # the first listed service.
        targets[services[0]] = bytes.fromhex(args.target)
    else:
        skips = _build_skip_hashes(getattr(args, "skip_self_identity", []), services)
        for service in services:
            handler = _make_announce_handler(
                service,
                DEFAULT_ASPECTS + [service],
                skips[service],
                targets,
                lock,
            )
            RNS.Transport.register_announce_handler(handler)
        RNS.log(
            f"[bridge:connect] services in priority order: "
            f"{services}; waiting up to {TARGET_DISCOVERY_TIMEOUT}s for "
            "the first announce on any of them",
            RNS.LOG_INFO,
        )
        if not _wait_for_any_target(targets, lock, services, TARGET_DISCOVERY_TIMEOUT):
            sys.exit(
                f"no announce on any of {services} within "
                f"{TARGET_DISCOVERY_TIMEOUT}s; cannot start without target"
            )

    tcp_host, tcp_port = args.tcp.rsplit(":", 1)
    tcp_port = int(tcp_port)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((tcp_host, tcp_port))
    listener.listen(8)
    with lock:
        snapshot = {s: targets.get(s) for s in services}
    RNS.log(
        f"[bridge:connect] listening on {tcp_host}:{tcp_port}, "
        f"fallback chain: {snapshot}",
        RNS.LOG_INFO,
    )

    while True:
        sock, addr = listener.accept()
        RNS.log(f"[bridge:connect] TCP connection from {addr}", RNS.LOG_INFO)
        threading.Thread(
            target=_handle_outbound,
            args=(sock, services, targets, lock),
            daemon=True,
        ).start()
