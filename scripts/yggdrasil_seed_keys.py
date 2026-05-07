#!/usr/bin/env python3
"""Splice a fresh Yggdrasil keypair into a config file in-place.

Reads the existing config text, asks `yggdrasil -genconf` for a fresh
keypair, and replaces the empty `PrivateKey: ""` / `PublicKey: ""`
placeholders with the new hex values. Any other content of the file —
comments, indentation, custom Listen/Peers, multicast settings — is
preserved byte-for-byte.

No-op when the keys are already populated.
"""

import re
import subprocess
import sys

from log_setup import get_logger

log = get_logger("yggdrasil_seed_keys")

PRIVATE_KEY_RE = re.compile(r"PrivateKey:\s*([0-9a-f]+)")


def fresh_keys():
    """Yggdrasil 0.5.x only emits a PrivateKey via -genconf; the
    PublicKey is derived at runtime and not stored on disk."""
    output = subprocess.check_output(["yggdrasil", "-genconf"], text=True)
    match = PRIVATE_KEY_RE.search(output)
    if not match:
        raise ValueError("`yggdrasil -genconf` produced no PrivateKey line")
    return {"PrivateKey": match.group(1)}


def splice(text, keys):
    return re.sub(
        r'PrivateKey:\s*""',
        f'PrivateKey: {keys["PrivateKey"]}',
        text,
        count=1,
    )


def main(path):
    with open(path) as fh:
        original = fh.read()
    if 'PrivateKey: ""' not in original:
        return 0
    try:
        keys = fresh_keys()
    except (subprocess.CalledProcessError, ValueError, AttributeError) as exc:
        log.error("cannot generate keys: %s", exc)
        return 0
    with open(path, "w") as fh:
        fh.write(splice(original, keys))
    log.info("keys written to %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/config/yggdrasil.conf"))
