"""Per-transport discovery plugins.

Each plugin pairs the announcer (`produce_endpoint`) with the
consumer (`consume_endpoint`) for one transport, so the generic
discovery loop in `discovery.py` does not need to know anything
service-specific.

Plugins are discovered by service name: a `mode: listen` bridge with
`service: yggdrasil` looks up a module named `yggdrasil` here. If the
module is missing the bridge silently runs without discovery.
"""

import importlib
from typing import Optional

from .base import DiscoveryPlugin


def load(service: str) -> Optional[DiscoveryPlugin]:
    try:
        module = importlib.import_module(f"{__name__}.{service}")
    except ImportError:
        return None
    factory = getattr(module, "plugin", None)
    return factory() if callable(factory) else None
