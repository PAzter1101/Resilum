"""Listen mode: accept incoming RNS Links and forward each to a fixed
TCP endpoint on the local machine."""

import socket
import threading
import time

import RNS

from .constants import (
    ANNOUNCE_INTERVAL_SECONDS,
    DEFAULT_ASPECTS,
    LINK_ESTABLISH_TIMEOUT,
)
from .identity import load_or_create_identity
from .pump import wire_link_to_socket


def _make_destination(identity, service):
    aspects = DEFAULT_ASPECTS + [service]
    destination = RNS.Destination(
        identity, RNS.Destination.IN, RNS.Destination.SINGLE, *aspects
    )
    destination.set_proof_strategy(RNS.Destination.PROVE_ALL)
    return destination, aspects


def _on_link_established(tcp_endpoint):
    tcp_host, tcp_port = tcp_endpoint

    def hookup(link):
        remote = link.get_remote_identity()
        peer = RNS.prettyhexrep(remote.hash) if remote else "<anonymous>"
        RNS.log(f"[bridge:listen] new Link from {peer}", RNS.LOG_INFO)
        try:
            sock = socket.create_connection(
                (tcp_host, tcp_port), timeout=LINK_ESTABLISH_TIMEOUT
            )
        except Exception as exc:
            RNS.log(
                f"[bridge:listen] cannot dial {tcp_host}:{tcp_port}: {exc}",
                RNS.LOG_ERROR,
            )
            link.teardown()
            return
        wire_link_to_socket(link, sock, label="listen")
        RNS.log("[bridge:listen] wired Link to local TCP socket", RNS.LOG_VERBOSE)

    def callback(link):
        # The link-established callback must return promptly: it is
        # invoked from Reticulum's packet-handling thread, and any
        # blocking work here delays the receipt of subsequent packets
        # on the same Link — including the very stream-data messages
        # we are about to start pumping.
        threading.Thread(target=hookup, args=(link,), daemon=True).start()

    return callback


def run(args):
    identity = load_or_create_identity(args.identity)
    destination, aspects = _make_destination(identity, args.service)
    tcp_endpoint = _parse_endpoint(args.tcp)

    RNS.log(
        f"[bridge:listen] destination {RNS.prettyhexrep(destination.hash)}, "
        f"forwarding incoming Links to {tcp_endpoint[0]}:{tcp_endpoint[1]}",
        RNS.LOG_INFO,
    )
    destination.set_link_established_callback(_on_link_established(tcp_endpoint))

    # Discovery is symmetric: a listen-mode bridge automatically
    # announces this node's transport endpoint and consumes others'
    # announcements, if a plugin for the service exists. Missing
    # plugin → bridge runs as a plain tunnel, no announce/discover.
    from . import discovery
    discovery.start(args.service, identity)

    while True:
        destination.announce()
        RNS.log(
            f"[bridge:listen] announced as {'.'.join(aspects)}",
            RNS.LOG_DEBUG,
        )
        time.sleep(ANNOUNCE_INTERVAL_SECONDS)


def _parse_endpoint(spec):
    host, port = spec.rsplit(":", 1)
    return host, int(port)
