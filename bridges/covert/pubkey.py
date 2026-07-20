"""Load a peer's public identity from its hex-encoded public key."""

import RNS


def identity_from_hex(pubhex: str):
    identity = RNS.Identity(create_keys=False)
    identity.load_public_key(bytes.fromhex(pubhex))
    return identity
