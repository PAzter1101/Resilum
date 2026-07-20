"""
Per-link key from RNS identities: the client seals a random session key
to the server's public identity; only the server's private key unseals it.
"""

import os

SESSION_KEY_LEN = 32


def new_session_key() -> bytes:
    return os.urandom(SESSION_KEY_LEN)


def seal(server_identity, key: bytes) -> bytes:
    token: bytes = server_identity.encrypt(key)
    return token


def unseal(own_identity, token: bytes) -> "bytes | None":
    try:
        key = own_identity.decrypt(token)
    except Exception:
        return None
    return key if key is not None and len(key) == SESSION_KEY_LEN else None
