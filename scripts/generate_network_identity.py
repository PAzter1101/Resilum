#!/usr/bin/env python3
"""Write a fresh Reticulum Identity to a path on disk.

Replaces ``rnid -g`` in the container entrypoint. ``rnid -g`` writes
the file fine but then loads the full Reticulum stack to validate it,
and that load never finishes when the configured bootstrap interfaces
can't reach their peers (typical first boot on a fresh VPS) — leaving
the entrypoint blocked on a process that has already done its job.

``RNS.Identity()`` is the documented public API for fresh identity
generation and only touches the in-process crypto state, so it
returns synchronously regardless of network reachability.
"""

import os
import sys

import RNS
from log_setup import get_logger

log = get_logger("generate_network_identity")


def main(path: str) -> int:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    RNS.Identity().to_file(path)
    # 0o600 because the file holds the Ed25519 private key — anyone
    # with read access to it can decrypt every message addressed to
    # this node. RNS itself does not chmod the output of to_file().
    os.chmod(path, 0o600)
    log.info("network identity written to %s", path)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        log.error("Usage: generate_network_identity.py <path>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
