"""Input validation and parsing for public-listen environment variables."""

import re

_PORT_MAX = 65535
_YGG_SCHEME_RE = re.compile(r"^(tcp|tls)://(.+)$")


def split_host_port(entry):
    entry = entry.strip()
    if entry.startswith("["):
        host, sep, port = entry.partition("]:")
        if not sep:
            raise ValueError(f"bad bracketed address: {entry!r}")
        return host[1:], port
    host, sep, port = entry.rpartition(":")
    if not sep:
        raise ValueError(f"missing port: {entry!r}")
    return host, port


def valid_port(port):
    return port.isdigit() and 1 <= int(port) <= _PORT_MAX


def parse_ygg_listen(value):
    uris = []
    for raw in value.split(","):
        entry = raw.strip()
        if not entry:
            raise ValueError("empty entry in RESILUM_YGG_PUBLIC_LISTEN")
        m = _YGG_SCHEME_RE.match(entry)
        if not m:
            raise ValueError(f"missing tcp://|tls:// scheme: {entry!r}")
        host, port = split_host_port(m.group(2))
        if not host or not valid_port(port):
            raise ValueError(f"bad address: {entry!r}")
        uris.append(entry)
    return uris


def parse_rns_listen(value):
    binds = []
    for raw in value.split(","):
        entry = raw.strip()
        if not entry:
            raise ValueError("empty entry in RESILUM_RNS_LISTEN")
        host, port = split_host_port(entry)
        if not host or not valid_port(port):
            raise ValueError(f"bad address: {entry!r}")
        binds.append((host, int(port)))
    return binds
