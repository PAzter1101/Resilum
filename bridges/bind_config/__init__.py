"""Public API for the bind-config package.

Re-exports every name consumed by scripts and tests so that
``import bind_config as rbc`` exposes the full surface.
"""

from bind_config.apply import main, render_file
from bind_config.parsing import (
    parse_rns_listen,
    parse_ygg_listen,
    split_host_port,
    valid_port,
)
from bind_config.regions import replace_region
from bind_config.render import render_rns, render_ygg, rns_block

__all__ = [
    "main",
    "parse_rns_listen",
    "parse_ygg_listen",
    "render_file",
    "render_rns",
    "render_ygg",
    "replace_region",
    "rns_block",
    "split_host_port",
    "valid_port",
]
