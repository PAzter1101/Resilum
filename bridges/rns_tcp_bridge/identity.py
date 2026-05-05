"""Identity persistence — load an RNS identity from disk, generate and
write one on first use."""

import os
import sys

import RNS


def load_or_create_identity(path):
    """Return an RNS identity stored at ``path``.

    The on-disk format is the plain serialised :class:`RNS.Identity`
    bytes (as written by :py:meth:`RNS.Identity.to_file`). Protect it
    with file-system permissions; it is *not* encrypted.
    """
    if os.path.isfile(path):
        identity = RNS.Identity.from_file(path)
        if identity is None:
            sys.exit(f"failed to load RNS identity from {path}")
        return identity

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    identity = RNS.Identity()
    identity.to_file(path)
    return identity
