"""Per-server ICMP echo id. Both endpoints derive it from the server's identity
— the client from the announced public key, the server from its own — so the
echo-reply suppression rule (nftguard) and the carrier agree on a marker without
a hardcoded constant. It is a deterministic function of the identity, so it
varies per server."""

import hashlib

_DOMAIN = b"resilum-covert-icmp-id"


def tunnel_id(server_pubkey: bytes) -> int:
    digest = hashlib.sha256(_DOMAIN + server_pubkey).digest()
    return int.from_bytes(digest[:2], "big") or 1
