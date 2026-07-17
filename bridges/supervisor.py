"""Spawn and supervise multiple long-running Resilum components from
one YAML config file.

The supervisor is intentionally tiny — it launches child processes and
restarts them with exponential backoff when they exit.

Run from the container entrypoint:

    python -m supervisor /config/bridges.yaml
"""

import argparse
import signal
import subprocess
import time

from bridge_config import load
from bridge_spawn import spawn
from log_setup import get_logger

log = get_logger("supervisor")

RESTART_BACKOFF = (1, 2, 5, 15, 30, 60)


def _tick(entry, specs):
    if entry["proc"].poll() is None:
        return
    if entry["next"] == 0.0:
        delay = RESTART_BACKOFF[min(entry["fails"], len(RESTART_BACKOFF) - 1)]
        entry["fails"] += 1
        entry["next"] = time.time() + delay
        log.warning(
            "%s exited (rc=%s); restart in %ds",
            type(entry["spec"]).__name__,
            entry["proc"].returncode,
            delay,
        )
    elif time.time() >= entry["next"]:
        entry["proc"] = spawn(entry["spec"], specs)
        entry["next"] = 0.0


def main() -> None:
    parser = argparse.ArgumentParser(prog="supervisor")
    parser.add_argument("config", help="path to bridges.yaml")
    args = parser.parse_args()
    specs = load(args.config)
    if not specs:
        log.info("nothing to run, exiting")
        return

    state = [
        {"spec": s, "proc": spawn(s, specs), "fails": 0, "next": 0.0} for s in specs
    ]

    stop = False

    def shutdown(_sig, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while not stop:
        time.sleep(1)
        for entry in state:
            _tick(entry, specs)

    for entry in state:
        if entry["proc"].poll() is None:
            entry["proc"].terminate()
    for entry in state:
        try:
            entry["proc"].wait(timeout=5)
        except subprocess.TimeoutExpired:
            entry["proc"].kill()


if __name__ == "__main__":
    main()
