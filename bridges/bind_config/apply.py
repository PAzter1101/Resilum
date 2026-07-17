"""File-level apply logic and CLI entry point for bind config rendering."""

import os

from bind_config.render import render_rns, render_ygg
from log_setup import get_logger

log = get_logger("render_bind_config")


def render_file(path, tag, env_name, render_fn):
    value = os.environ.get(env_name)
    if value is None:
        return
    with open(path) as fh:
        original = fh.read()
    try:
        updated = render_fn(original, value)
    except ValueError as exc:
        log.error("invalid %s: %s", env_name, exc)
        raise SystemExit(2)
    if updated is None:
        log.warning(
            "%s is set but %s has no resilum:managed region; "
            "value ignored — add markers or migrate the config",
            env_name,
            path,
        )
        return
    with open(path, "w") as fh:
        fh.write(updated)
    log.info("rendered %s region in %s", tag, path)


def main(argv):
    ygg_path = argv[1] if len(argv) > 1 else "/config/yggdrasil.conf"
    rns_dir = os.environ.get("RNS_CONFIG_DIR", "/config/reticulum")
    rns_path = argv[2] if len(argv) > 2 else os.path.join(rns_dir, "config")
    render_file(ygg_path, "ygg-public-listen", "RESILUM_YGG_PUBLIC_LISTEN", render_ygg)
    render_file(rns_path, "rns-public-listen", "RESILUM_RNS_LISTEN", render_rns)
    return 0
