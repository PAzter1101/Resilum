"""Carrier plugins, loaded by name (mirrors rns_tcp_bridge.discovery_plugins)."""

import importlib
from typing import Optional

from .base import Carrier


def load(name: str, **opts) -> Optional[Carrier]:
    try:
        module = importlib.import_module(f"{__name__}.{name}")
    except ImportError:
        return None
    factory = getattr(module, "carrier", None)
    return factory(**opts) if callable(factory) else None
