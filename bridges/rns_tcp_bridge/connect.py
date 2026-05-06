"""Connect mode: listen on a local TCP port and tunnel each connection
through an RNS Link to a known anchor identity."""

import socket
import sys
import threading
import time

import RNS

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


def _handle_outbound(sock, target_hash, aspects):
    RNS.log(
        f"[bridge:connect] resolving target {RNS.prettyhexrep(target_hash)}",
        RNS.LOG_VERBOSE,
    )
    target_dest = _resolve_target(target_hash, aspects)
    if target_dest is None:
        RNS.log(
            f"[bridge:connect] no path to {RNS.prettyhexrep(target_hash)} "
            f"after {PATH_REQUEST_TIMEOUT}s, dropping TCP connection",
            RNS.LOG_WARNING,
        )
        sock.close()
        return

    RNS.log("[bridge:connect] target resolved, opening Link", RNS.LOG_VERBOSE)
    link = _open_link(target_dest, target_hash)
    if link is None:
        sock.close()
        return

    RNS.log("[bridge:connect] Link active, wiring TCP", RNS.LOG_VERBOSE)
    wire_link_to_socket(link, sock, label="connect")


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
    # OUT-mode Destination computes the same hash as IN-mode but does
    # not register with Transport, so this won't conflict with the real
    # listen-bridge running in a sibling process.
    sibling = RNS.Destination(
        identity, RNS.Destination.OUT, RNS.Destination.SINGLE, *aspects
    )
    return sibling.hash


def _wait_for_announced_target(
    aspects: list, timeout: float, skip_hashes: set[bytes]
) -> bytes | None:
    """Block until an RNS announce on the joined aspects arrives from
    a destination not in ``skip_hashes``, then return that hash. The
    listen-side bridge announces every ANNOUNCE_INTERVAL_SECONDS, so
    we only need to hear one matching announce."""
    discovered: list[bytes] = []
    seen = threading.Event()
    aspect_filter = ".".join(aspects)

    class _Handler:
        # RNS' AnnounceHandler API is duck-typed by attribute name.
        # `aspect_filter` narrows what announces we receive;
        # `receive_path_responses=False` is the conventional value
        # for non-Transport handlers.
        def __init__(self):
            self.aspect_filter = aspect_filter
            self.receive_path_responses = False

        def received_announce(self, destination_hash, announced_identity, app_data):
            del announced_identity, app_data  # unused but required by RNS API
            if destination_hash in skip_hashes:
                RNS.log(
                    f"[bridge:connect] ignoring announce from self "
                    f"{RNS.prettyhexrep(destination_hash)}",
                    RNS.LOG_DEBUG,
                )
                return
            discovered.append(destination_hash)
            seen.set()

    handler = _Handler()
    RNS.Transport.register_announce_handler(handler)
    try:
        return discovered[0] if seen.wait(timeout) else None
    finally:
        try:
            RNS.Transport.deregister_announce_handler(handler)
        except Exception:
            pass


def run(args):
    load_or_create_identity(args.identity)
    aspects = DEFAULT_ASPECTS + [args.service]

    if args.target:
        target_hash = bytes.fromhex(args.target)
    else:
        skip_hashes: set[bytes] = set()
        for path in getattr(args, "skip_self_identity", []) or []:
            h = _hash_from_identity_file(path, aspects)
            if h is not None:
                skip_hashes.add(h)
                RNS.log(
                    f"[bridge:connect] will skip self-announce "
                    f"{RNS.prettyhexrep(h)} (from {path})",
                    RNS.LOG_VERBOSE,
                )
        RNS.log(
            f"[bridge:connect] no --target given, listening for announces on "
            f"{'.'.join(aspects)} (timeout {TARGET_DISCOVERY_TIMEOUT}s, "
            f"{len(skip_hashes)} self-hashes ignored)",
            RNS.LOG_INFO,
        )
        target_hash = _wait_for_announced_target(
            aspects, TARGET_DISCOVERY_TIMEOUT, skip_hashes
        )
        if target_hash is None:
            sys.exit(
                f"no non-self announce on {'.'.join(aspects)} within "
                f"{TARGET_DISCOVERY_TIMEOUT}s; cannot start without target"
            )
        RNS.log(
            f"[bridge:connect] auto-discovered target "
            f"{RNS.prettyhexrep(target_hash)}",
            RNS.LOG_INFO,
        )

    tcp_host, tcp_port = args.tcp.rsplit(":", 1)
    tcp_port = int(tcp_port)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((tcp_host, tcp_port))
    listener.listen(8)
    RNS.log(
        f"[bridge:connect] listening on {tcp_host}:{tcp_port}, "
        f"target {RNS.prettyhexrep(target_hash)}",
        RNS.LOG_INFO,
    )

    while True:
        sock, addr = listener.accept()
        RNS.log(f"[bridge:connect] TCP connection from {addr}", RNS.LOG_INFO)
        threading.Thread(
            target=_handle_outbound,
            args=(sock, target_hash, aspects),
            daemon=True,
        ).start()
