"""Connect mode: listen on a local TCP port and tunnel each accepted
connection through an RNS Link to a known anchor identity.

Supports a priority list of services so a single TCP endpoint can
fall through transports — e.g. try ``socks-egress`` first (direct
public-IP exit), fall back to ``tor`` (Tor SOCKS via mesh) if the
direct egress is unreachable. Both the discovery half (announce
handlers) and the dispatch half (per-connection target picker) honour
the order in which services were given on the command line."""

import socket
import sys
import threading

import RNS

from ..constants import DEFAULT_ASPECTS
from ..identity import load_or_create_identity
from .announce import _build_skip_hashes, _make_announce_handler
from .dispatch import _handle_outbound, _wait_for_any_target

TARGET_DISCOVERY_TIMEOUT = 90


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
