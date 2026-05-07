"""Resilum release version and the peer-compatibility predicate.

VERSION is read from the ``RESILUM_VERSION`` env var (injected at
container build time from the semantic-release tag); local
unconfigured builds default to ``"0.0.0"`` so they fall into the
0.x compatibility bucket alongside tagged 0.x releases.

Compatibility rule: peers are compatible iff their semver majors
match. The wire format is allowed to change in any non-major bump,
including across 0.x → 0.(x+1), so operators get push-button
incompatibility detection without needing a separate protocol
counter to bump.
"""

import os
import re
from typing import Optional

VERSION = os.environ.get("RESILUM_VERSION") or "0.0.0"

_SEMVER_RE = re.compile(r"^(\d+)\.\d+\.\d+(?:[-+].*)?$")


def _major(raw: str) -> Optional[int]:
    match = _SEMVER_RE.match(raw)
    if not match:
        return None
    return int(match.group(1))


def is_compatible(other: str, *, ours: str = VERSION) -> bool:
    """True iff a peer announcing ``other`` is on a compatible Resilum
    release for the local node running ``ours``."""
    o = _major(ours)
    p = _major(other)
    if o is None or p is None:
        return False
    return o == p
