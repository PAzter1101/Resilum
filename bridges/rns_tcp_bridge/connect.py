"""Connect mode: listen on a local TCP port and tunnel each connection
through an RNS Link to a known anchor identity."""

import socket
import sys
import threading
import time

import RNS

from .constants import (
    DEFAULT_ASPECTS,
    LINK_ESTABLISH_TIMEOUT,
    PATH_REQUEST_TIMEOUT,
)
from .identity import load_or_create_identity
from .pump import wire_link_to_socket


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
        remote_identity, RNS.Destination.OUT,
        RNS.Destination.SINGLE, *aspects,
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
    RNS.log(f"[bridge:connect] resolving target {RNS.prettyhexrep(target_hash)}", RNS.LOG_VERBOSE)
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


def run(args):
    if not args.target:
        sys.exit(
            "connect mode currently requires --target <hex-hash>; "
            "automatic discovery via aspect-only path-request is on the roadmap"
        )

    load_or_create_identity(args.identity)
    aspects     = DEFAULT_ASPECTS + [args.service]
    target_hash = bytes.fromhex(args.target)
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
