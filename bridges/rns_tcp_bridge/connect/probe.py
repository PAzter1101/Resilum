"""End-to-end egress probe: open a dedicated Link, run one SOCKS5
CONNECT to a neutral reference target, and time the reply.

Each probe uses its own ephemeral Link. On the egress (listen) side a
Link maps one-to-one onto a single TCP/SOCKS session, so a Link can
carry exactly one CONNECT — reusing a warm Link for repeated probes
would inject bytes into an already-open tunnel."""

import os
import socket
import struct
import threading
import time

import RNS
from RNS.Buffer import RawChannelReader, RawChannelWriter

from ..constants import DEFAULT_ASPECTS, LINK_ESTABLISH_TIMEOUT
from .candidates import Candidate
from .dispatch import _resolve_target

PROBE_TIMEOUT = 20.0
# Neutral, geographically diverse anycast targets on 443. Tried in order
# so one unreachable target does not falsely mark an egress unhealthy.
DEFAULT_PROBE_TARGETS = [("1.1.1.1", 443), ("8.8.8.8", 443), ("9.9.9.9", 443)]
# Operators override via env: comma-separated IPv4:port, e.g.
#   RESILUM_EGRESS_PROBE_TARGETS="1.1.1.1:443,9.9.9.9:443"
PROBE_TARGETS_ENV = "RESILUM_EGRESS_PROBE_TARGETS"


def _parse_entries(entries: list) -> list:
    """Parse ``host:port`` items; malformed ones are logged and skipped."""
    targets = []
    for item in entries:
        entry = item.strip()
        if not entry:
            continue
        parsed = _parse_one(entry)
        if parsed is None:
            RNS.log(
                f"[bridge:connect] ignoring malformed probe target "
                f"{entry!r}; expected IPv4:port",
                RNS.LOG_WARNING,
            )
        else:
            targets.append(parsed)
    return targets


def parse_targets(raw: "str | None") -> list:
    """Parse a comma-separated env value; falls back to built-in defaults
    when unset or all entries are invalid."""
    if not raw or not raw.strip():
        return list(DEFAULT_PROBE_TARGETS)
    targets = _parse_entries(raw.split(","))
    if not targets:
        RNS.log(
            f"[bridge:connect] no valid {PROBE_TARGETS_ENV} entries; "
            "using built-in probe targets",
            RNS.LOG_WARNING,
        )
        return list(DEFAULT_PROBE_TARGETS)
    return targets


def resolve_targets(cli_targets: "list | None") -> list:
    """Resolve probe targets by precedence: explicit CLI targets (from
    bridges.yaml) override the env var, which overrides built-in defaults."""
    if cli_targets:
        targets = _parse_entries(cli_targets)
        if targets:
            return targets
    return parse_targets(os.environ.get(PROBE_TARGETS_ENV))


def _parse_one(entry: str) -> "tuple[str, int] | None":
    host, _, port = entry.rpartition(":")
    if not host or not port.isdigit():
        return None
    port_num = int(port)
    if not 0 < port_num <= 65535:
        return None
    try:
        socket.inet_aton(host)
    except OSError:
        return None
    return host, port_num


def _open_link(candidate: Candidate) -> "RNS.Link | None":
    dest = _resolve_target(candidate.dest_hash, DEFAULT_ASPECTS + [candidate.service])
    if dest is None:
        return None
    link = RNS.Link(dest)
    deadline = time.time() + LINK_ESTABLISH_TIMEOUT
    while time.time() < deadline and link.status != RNS.Link.ACTIVE:
        time.sleep(0.1)
    if link.status != RNS.Link.ACTIVE:
        link.teardown()
        return None
    return link


def _socks_connect(link: "RNS.Link", host: str, port: int) -> "float | None":
    """One SOCKS5 CONNECT over ``link``'s channel; seconds to reply or None."""
    greeting = b"\x05\x01\x00"  # VER=5 NMETHODS=1 METHOD=0 (no-auth)
    connect_req = struct.pack("!BBBB4sH", 5, 1, 0, 1, socket.inet_aton(host), port)

    channel = link.get_channel()
    writer = RawChannelWriter(0, channel)
    reader = RawChannelReader(0, channel)

    reply_buf: list = []
    reply_event = threading.Event()

    def _on_data(ready):
        chunk = bytearray(ready)
        n = reader.readinto(chunk)
        if n:
            reply_buf.append(bytes(chunk[:n]))
        # await 2-byte greeting reply + 10-byte CONNECT reply (IPv4)
        if sum(len(b) for b in reply_buf) >= 12:
            reply_event.set()

    reader.add_ready_callback(_on_data)
    try:
        writer.write(greeting + connect_req)
        t0 = time.monotonic()
        if not reply_event.wait(timeout=PROBE_TIMEOUT):
            return None
        return time.monotonic() - t0
    except Exception:
        return None
    finally:
        try:
            reader.remove_ready_callback(_on_data)
        except Exception:
            pass


def e2e_probe(candidate: Candidate, targets: list) -> "float | None":
    """Round-trip seconds through the egress to the first reachable probe
    target, or None if the Link cannot be opened or every target fails."""
    for host, port in targets:
        link = _open_link(candidate)
        if link is None:
            return None
        try:
            rtt = _socks_connect(link, host, port)
        finally:
            link.teardown()
        if rtt is not None:
            return rtt
    return None
