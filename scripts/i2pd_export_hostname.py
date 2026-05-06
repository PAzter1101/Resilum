#!/usr/bin/env python3
"""Wait for i2pd to materialise its server-tunnel keys file and write
the matching .b32.i2p hostname to a separate text file.

i2pd derives a destination's .b32.i2p hostname as
``base32(sha256(first 391 bytes of keys.dat))``. The 391-byte prefix
covers the public key (384) plus a 7-byte certificate for the default
EdDSA-25519 signature type — non-default sigtypes have a different
prefix length and would need a different number here.

Idempotent: if the hostname file already exists, exit immediately.
Polls the keys file until it appears (i2pd creates it shortly after
startup), with a generous timeout so a never-starting i2pd doesn't
wedge the entrypoint forever.
"""

import base64
import hashlib
import os
import sys
import time

DESTINATION_PREFIX_BYTES = 391
KEYS_WAIT_TIMEOUT_SECONDS = 600
KEYS_POLL_INTERVAL_SECONDS = 2


def derive_hostname(keys_path: str) -> str:
    with open(keys_path, "rb") as fh:
        prefix = fh.read(DESTINATION_PREFIX_BYTES)
    if len(prefix) < DESTINATION_PREFIX_BYTES:
        raise ValueError(
            f"{keys_path} has only {len(prefix)} bytes, "
            f"expected at least {DESTINATION_PREFIX_BYTES}"
        )
    digest = hashlib.sha256(prefix).digest()
    b32 = base64.b32encode(digest).decode().rstrip("=").lower()
    return f"{b32}.b32.i2p"


def wait_for_keys(path: str, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(path) and os.path.getsize(path) >= DESTINATION_PREFIX_BYTES:
            return True
        time.sleep(KEYS_POLL_INTERVAL_SECONDS)
    return False


def main(keys_path: str, hostname_path: str) -> int:
    if os.path.exists(hostname_path):
        return 0
    if not wait_for_keys(keys_path, KEYS_WAIT_TIMEOUT_SECONDS):
        print(
            f"[i2pd_export_hostname] {keys_path} did not appear within "
            f"{KEYS_WAIT_TIMEOUT_SECONDS}s; i2pd never published a tunnel",
            file=sys.stderr,
        )
        return 1
    hostname = derive_hostname(keys_path)
    os.makedirs(os.path.dirname(hostname_path), exist_ok=True)
    with open(hostname_path, "w") as fh:
        fh.write(hostname + "\n")
    print(f"[i2pd_export_hostname] {hostname} → {hostname_path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Usage: i2pd_export_hostname.py <keys.dat> <hostname-out>",
            file=sys.stderr,
        )
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
