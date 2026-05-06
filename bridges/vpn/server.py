"""VPN server (anchor side).

Sets up a TUN device on the host, configures NAT/forwarding rules so
the host kernel forwards client traffic out through ``--uplink``,
listens for incoming RNS Links on the destination
``resilum.vpn.gateway``, allocates a private IP per client and pumps
IP packets between each Link and the TUN.
"""

import ipaddress
import os
import subprocess
import threading
import time

import RNS

from . import framing, pump, tun

VPN_ASPECTS = ["resilum", "vpn", "gateway"]


def _enable_forwarding(uplink: str, subnet: str) -> None:
    subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], check=True)
    subprocess.run(
        ["iptables", "-t", "nat", "-A", "POSTROUTING",
         "-s", subnet, "-o", uplink, "-j", "MASQUERADE"],
        check=True,
    )
    subprocess.run(["iptables", "-A", "FORWARD", "-i", uplink,
                    "-m", "state", "--state", "RELATED,ESTABLISHED",
                    "-j", "ACCEPT"], check=True)
    subprocess.run(["iptables", "-A", "FORWARD", "-s", subnet,
                    "-o", uplink, "-j", "ACCEPT"], check=True)


class _Allocator:
    """Hand out one /32 from the pool per client; release on
    disconnect. The first usable host of the pool is reserved for
    the server's TUN address."""

    def __init__(self, subnet: ipaddress.IPv4Network):
        self._subnet  = subnet
        self._free    = [str(ip) for ip in list(subnet.hosts())[1:]]
        self._lock    = threading.Lock()
        self.server_ip = str(list(subnet.hosts())[0])

    def acquire(self) -> str | None:
        with self._lock:
            return self._free.pop(0) if self._free else None

    def release(self, ip: str) -> None:
        with self._lock:
            if ip not in self._free:
                self._free.append(ip)


def _serve_link(link, allocator: _Allocator, server_fd: int,
                subnet: ipaddress.IPv4Network) -> None:
    client_ip = allocator.acquire()
    if client_ip is None:
        RNS.log("[vpn:server] address pool exhausted, refusing link",
                RNS.LOG_WARNING)
        link.teardown()
        return

    # Single-line handshake: "VPN/1 <client-ip> <server-ip> <prefix>\n"
    handshake = f"VPN/1 {client_ip} {allocator.server_ip} {subnet.prefixlen}\n".encode()
    channel = link.get_channel()
    from RNS.Buffer import RawChannelWriter
    RawChannelWriter(0, channel).write(framing.encode(handshake))

    closed = pump.wire(link, server_fd, label=f"server[{client_ip}]")
    RNS.log(f"[vpn:server] {client_ip} connected", RNS.LOG_INFO)

    def cleanup():
        closed.wait()
        allocator.release(client_ip)
        RNS.log(f"[vpn:server] {client_ip} disconnected", RNS.LOG_INFO)

    threading.Thread(target=cleanup, daemon=True).start()


def run(args) -> None:
    subnet  = ipaddress.IPv4Network(args.subnet, strict=False)
    alloc   = _Allocator(subnet)

    fd = tun.open_tun(args.tun)
    tun.configure(args.tun, alloc.server_ip, subnet.prefixlen, args.mtu)
    _enable_forwarding(args.uplink, str(subnet))

    from rns_tcp_bridge.identity import load_or_create_identity
    identity = load_or_create_identity(args.identity)

    destination = RNS.Destination(
        identity, RNS.Destination.IN, RNS.Destination.SINGLE, *VPN_ASPECTS,
    )
    destination.set_proof_strategy(RNS.Destination.PROVE_ALL)
    destination.set_link_established_callback(
        lambda link: threading.Thread(
            target=_serve_link, args=(link, alloc, fd, subnet), daemon=True,
        ).start()
    )

    RNS.log(f"[vpn:server] listening as {RNS.prettyhexrep(destination.hash)} "
            f"on TUN {args.tun} ({alloc.server_ip}/{subnet.prefixlen}), "
            f"NATing through {args.uplink}", RNS.LOG_INFO)

    while True:
        destination.announce()
        time.sleep(6 * 60 * 60)
