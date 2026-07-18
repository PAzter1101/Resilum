"""Discovery endpoint wire form: <carrier>:<addr> (e.g. icmp:203.0.113.9)."""


def pack_endpoint(carrier: str, addr: str) -> bytes:
    return f"{carrier}:{addr}".encode()


def parse_endpoint(raw: bytes) -> "tuple[str, str] | None":
    try:
        carrier, addr = raw.decode().split(":", 1)
    except (ValueError, UnicodeDecodeError):
        return None
    return (carrier, addr) if carrier and addr else None
