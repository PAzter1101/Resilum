"""Connect mode: listen on a local TCP port and forward each accepted
connection through the fastest eligible egress candidate, chosen per
connection by the registry+selector and kept sticky for the lifetime
of that connection.

The listener always binds immediately; when no candidate is known yet
the connection is dropped with a warning instead of blocking startup."""

import socket
import threading

import RNS

from ..constants import DEFAULT_ASPECTS
from ..identity import load_or_create_identity
from . import monitor
from .announce import _build_skip_hashes, _make_registry_handler
from .candidates import CandidateRegistry
from .dispatch import dispatch_to
from .eligibility import eligible
from .probe import resolve_targets
from .selector import choose_best


def _serve(sock, candidate):
    if not dispatch_to(sock, candidate):
        sock.close()


def run(args):
    load_or_create_identity(args.identity)
    services = list(args.service) if args.service else ["generic"]
    use_own = getattr(args, "use_own", "smart")
    allow = list(getattr(args, "allow_country", []) or [])
    deny = list(getattr(args, "deny_country", []) or [])

    registry = CandidateRegistry()

    if args.target:
        # Explicit --target: dial a fixed hash directly, bypassing discovery.
        registry.upsert(services[0], bytes.fromhex(args.target))
        skip_hashes: dict[str, set] = {s: set() for s in services}
    else:
        skip_hashes = _build_skip_hashes(
            getattr(args, "skip_self_identity", []), services
        )
        for service in services:
            handler = _make_registry_handler(
                service, DEFAULT_ASPECTS + [service], skip_hashes[service], registry
            )
            RNS.Transport.register_announce_handler(handler)

    def eligible_now():
        return eligible(registry.all(), use_own, allow, deny, skip_hashes)

    probe_targets = resolve_targets(getattr(args, "probe_target", None))

    threading.Thread(
        target=monitor.run,
        args=(registry, lambda _all: eligible_now(), probe_targets),
        daemon=True,
        name="egress-monitor",
    ).start()

    tcp_host, tcp_port = args.tcp.rsplit(":", 1)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((tcp_host, int(tcp_port)))
    listener.listen(8)
    RNS.log(
        f"[bridge:connect] listening on {tcp_host}:{tcp_port}, services={services}",
        RNS.LOG_INFO,
    )

    current = None
    while True:
        sock, addr = listener.accept()
        RNS.log(f"[bridge:connect] TCP connection from {addr}", RNS.LOG_INFO)
        current = choose_best(eligible_now(), current)
        if current is None:
            RNS.log(
                "[bridge:connect] no eligible egress; dropping connection",
                RNS.LOG_WARNING,
            )
            sock.close()
            continue
        threading.Thread(target=_serve, args=(sock, current), daemon=True).start()
