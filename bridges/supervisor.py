"""Spawn and supervise multiple ``rns_tcp_bridge`` instances from a
single YAML config file.

The supervisor itself is intentionally tiny — it does not parse RNS
state, share a Reticulum instance, or do anything clever. It only
launches child processes and restarts them with exponential backoff
when they exit.

Run from the container entrypoint:

    python -m bridges.supervisor /config/bridges.yaml
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

import yaml

BRIDGE_MODULE  = "rns_tcp_bridge"
RESTART_BACKOFF = (1, 2, 5, 15, 30, 60)
RNS_CONFIG_DIR  = os.environ.get("RNS_CONFIG_DIR", "/config/reticulum")


@dataclass
class Spec:
    mode: str         # "listen" | "connect"
    service: str
    identity: str
    tcp: str
    target: str | None = None


def load(path):
    with open(path) as fh:
        doc = yaml.safe_load(fh) or {}
    out = []
    for i, entry in enumerate(doc.get("bridges", [])):
        mode = entry.get("mode")
        if mode not in ("listen", "connect"):
            sys.exit(f"bridges[{i}].mode must be 'listen' or 'connect', got {mode!r}")
        if mode == "connect" and not entry.get("target"):
            sys.exit(f"bridges[{i}] is connect-mode but has no 'target'")
        out.append(Spec(
            mode=mode, service=entry.get("service", "generic"),
            identity=entry["identity"], tcp=entry["tcp"],
            target=entry.get("target"),
        ))
    return out


def spawn(spec):
    cmd = [
        sys.executable, "-u", "-m", BRIDGE_MODULE,
        "--config", RNS_CONFIG_DIR,
        spec.mode,
        "--identity", spec.identity,
        "--service", spec.service,
        "--tcp", spec.tcp,
    ]
    if spec.target:
        cmd += ["--target", spec.target]
    print(f"[supervisor] spawning {spec.mode}/{spec.service}", flush=True)
    return subprocess.Popen(cmd)


def main():
    parser = argparse.ArgumentParser(prog="bridges.supervisor")
    parser.add_argument("config", help="path to bridges.yaml")
    args = parser.parse_args()

    specs = load(args.config)
    if not specs:
        print("[supervisor] no bridges configured, exiting", flush=True)
        return

    state = [{"spec": s, "proc": spawn(s), "fails": 0, "next": 0.0} for s in specs]

    stop = False
    def shutdown(_sig, _frame):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while not stop:
        time.sleep(1)
        for entry in state:
            proc = entry["proc"]
            if proc.poll() is None:
                continue
            if entry["next"] == 0.0:
                delay = RESTART_BACKOFF[min(entry["fails"], len(RESTART_BACKOFF) - 1)]
                entry["fails"] += 1
                entry["next"]   = time.time() + delay
                print(f"[supervisor] {entry['spec'].mode}/{entry['spec'].service} "
                      f"exited (rc={proc.returncode}); restart in {delay}s", flush=True)
            elif time.time() >= entry["next"]:
                entry["proc"] = spawn(entry["spec"])
                entry["next"] = 0.0

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
