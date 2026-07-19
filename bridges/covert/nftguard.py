"""Suppress the kernel's echo-reply for our tunnel packets only. Without this a
covert server answers each request twice — once from the kernel, once with our
crafted reply — doubling an already narrow channel. The rule matches this
server's echo id (see covert.icmpid), so every other ping is still answered
normally.

libpcap taps the wire before netfilter, so scapy still captures the dropped
requests."""

import atexit
import subprocess

_TABLE = "resilum_covert"


def _nft(*args: str) -> bool:
    try:
        subprocess.run(["nft", *args], check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _drop_rule(proto: str, ident: int) -> tuple:
    return (
        "add",
        "rule",
        "inet",
        _TABLE,
        "input",
        proto,
        "type",
        "echo-request",
        proto,
        "id",
        str(ident),
        "drop",
    )


def install(ident: int) -> bool:
    remove()
    ok = (
        _nft("add", "table", "inet", _TABLE)
        and _nft(
            "add",
            "chain",
            "inet",
            _TABLE,
            "input",
            "{ type filter hook input priority 0; policy accept; }",
        )
        and _nft(*_drop_rule("icmp", ident))
        and _nft(*_drop_rule("icmpv6", ident))
    )
    if ok:
        atexit.register(remove)
    else:
        remove()
    return ok


def remove() -> None:
    _nft("delete", "table", "inet", _TABLE)
