"""Covert transport entry point: covert <carrier> <client|server>."""

import argparse
import os
import queue
import sys
import threading
import time

from rns_tcp_bridge.identity import load_or_create_identity

from .carriers import load
from .carriers.icmp import DEFAULT_MTU
from .engine import ClientEngine, ServerEngine
from .icmpid import tunnel_id
from .pubkey import identity_from_hex

POLL_TICK = 0.1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="covert")
    p.add_argument("carrier")
    p.add_argument("role", choices=["client", "server"])
    p.add_argument("--identity", default="")
    p.add_argument("--server-identity", dest="server_identity", default="")
    p.add_argument("--dst", default="")
    p.add_argument("--interface", default="")
    p.add_argument("--mtu", type=int, default=DEFAULT_MTU)
    return p


def _emit(data: bytes) -> None:
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _read_stdin(q: queue.Queue) -> None:
    for chunk in iter(lambda: sys.stdin.buffer.read(4096), b""):
        q.put(("tx", chunk))
    q.put(("eof", None))


def _drive(carrier, engine, feed) -> None:
    q: queue.Queue = queue.Queue()
    threading.Thread(
        target=lambda: carrier.sniff(lambda raw: q.put(("rx", raw)), stop=None),
        daemon=True,
    ).start()
    threading.Thread(target=_read_stdin, args=(q,), daemon=True).start()
    while True:
        try:
            kind, data = q.get(timeout=POLL_TICK)
        except queue.Empty:
            kind = None
        now = time.monotonic()
        if kind == "rx":
            engine.on_received(data, now)
        elif kind == "tx":
            feed(data)
        elif kind == "eof":
            return
        engine.poll(now)


def _run_client(carrier, server) -> None:
    session_id = int.from_bytes(os.urandom(4), "big")
    engine = ClientEngine(carrier, server, session_id, on_output=_emit)
    _drive(carrier, engine, engine.write)


def _run_server(carrier, identity) -> None:
    engine = ServerEngine(carrier, identity, on_output=lambda peer, b: _emit(b))
    _drive(carrier, engine, engine.broadcast)


def _load_carrier(args, identity):
    carrier = load(
        args.carrier,
        dst=args.dst,
        iface=args.interface,
        ident=tunnel_id(identity.get_public_key()),
        mtu=args.mtu,
    )
    if carrier is None:
        sys.exit(f"unknown carrier {args.carrier!r}")
    return carrier


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    if args.role == "client":
        if not args.server_identity:
            sys.exit("client requires --server-identity")
        server = identity_from_hex(args.server_identity)
        _run_client(_load_carrier(args, server), server)
    else:
        if not args.identity:
            sys.exit("server requires --identity")
        identity = load_or_create_identity(args.identity)
        _run_server(_load_carrier(args, identity), identity)
