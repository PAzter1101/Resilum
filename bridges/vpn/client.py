"""VPN client (leaf side).

Discovers anchors automatically by listening for RNS announces on
``resilum.vpn.gateway``, opens an RNS Link to the closest one,
receives an IP allocation through a one-line handshake, brings up a
local TUN device with that address, points the host's default route
at it (unless ``--no-default-route`` is set) and pumps IP packets
between TUN and Link until either side tears down. On disconnect it
picks the next discovered anchor and reconnects.
"""

import os
import re
import sys
import time

import RNS
from RNS.Buffer import RawChannelReader

from . import framing, pump, tun
from .discovery import GatewayDiscovery
from .server import VPN_ASPECTS

LINK_TIMEOUT      = 30
HANDSHAKE_TIMEOUT = 15
DISCOVERY_TIMEOUT = 300                  # how long to wait for first announce
HANDSHAKE_RE = re.compile(rb"^VPN/1 (\S+) (\S+) (\d+)$")


def _await_link(target_hash: bytes) -> RNS.Link | None:
    if not RNS.Transport.has_path(target_hash):
        RNS.Transport.request_path(target_hash)
        deadline = time.time() + LINK_TIMEOUT
        while time.time() < deadline and not RNS.Transport.has_path(target_hash):
            time.sleep(0.1)
        if not RNS.Transport.has_path(target_hash):
            return None

    remote = RNS.Identity.recall(target_hash)
    if remote is None:
        return None
    target_dest = RNS.Destination(
        remote, RNS.Destination.OUT, RNS.Destination.SINGLE, *VPN_ASPECTS,
    )
    link = RNS.Link(target_dest)
    deadline = time.time() + LINK_TIMEOUT
    while time.time() < deadline and link.status != RNS.Link.ACTIVE:
        time.sleep(0.1)
    return link if link.status == RNS.Link.ACTIVE else None


def _read_handshake(link) -> tuple[str, str, int] | None:
    reader  = RawChannelReader(0, link.get_channel())
    decoder = framing.StreamDecoder()
    deadline = time.time() + HANDSHAKE_TIMEOUT
    while time.time() < deadline:
        time.sleep(0.1)
        chunk = bytearray(4096)
        n = reader.readinto(chunk)
        if not n:
            continue
        for packet in decoder.feed(bytes(chunk[:n])):
            match = HANDSHAKE_RE.match(packet.strip())
            if match:
                return match.group(1).decode(), match.group(2).decode(), int(match.group(3))
    return None


def _resolve_target(args) -> bytes | None:
    if args.target:
        return bytes.fromhex(args.target)
    discovery = GatewayDiscovery()
    RNS.Transport.register_announce_handler(discovery)
    RNS.log("[vpn:client] no --target given, waiting for VPN-anchor announce…",
            RNS.LOG_INFO)
    return discovery.wait_for_one(DISCOVERY_TIMEOUT)


def run(args) -> None:
    from rns_tcp_bridge.identity import load_or_create_identity
    load_or_create_identity(args.identity)

    target_hash = _resolve_target(args)
    if target_hash is None:
        sys.exit("no VPN anchor heard within "
                 f"{DISCOVERY_TIMEOUT}s — none reachable on the mesh?")
    RNS.log(f"[vpn:client] using anchor {RNS.prettyhexrep(target_hash)}",
            RNS.LOG_INFO)
    link = _await_link(target_hash)
    if link is None:
        sys.exit(f"could not establish Link to {args.target}")

    handshake = _read_handshake(link)
    if handshake is None:
        link.teardown()
        sys.exit("server did not send a VPN handshake within timeout")
    client_ip, gateway_ip, prefix = handshake

    fd = tun.open_tun(args.tun)
    tun.configure(args.tun, client_ip, prefix, args.mtu)

    previous = None
    if not args.no_default_route:
        previous = tun.replace_default_route(args.tun, gateway_ip)

    RNS.log(f"[vpn:client] up: {client_ip}/{prefix} via {gateway_ip} "
            f"(tun={args.tun})", RNS.LOG_INFO)

    closed = pump.wire(link, fd, label="client")
    try:
        closed.wait()
    finally:
        tun.restore_default_route(previous)
        try:
            os.close(fd)
        except OSError:
            pass
        tun.teardown(args.tun)
