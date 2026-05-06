"""Spawn and supervise multiple long-running Resilum components from
one YAML config file.

The supervisor is intentionally tiny — it only launches child
processes and restarts them with exponential backoff when they exit.
Two component families are recognised today:

  * ``bridges:`` — `rns_tcp_bridge listen|connect` instances.
  * ``vpn:``     — `bridges.vpn server|client` instances.

Adding a new family is one extra parser + one extra `_spawn_*`
function below; the main loop is generic.

Run from the container entrypoint:

    python -m supervisor /config/bridges.yaml
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

import yaml

RESTART_BACKOFF = (1, 2, 5, 15, 30, 60)
RNS_CONFIG_DIR = os.environ.get("RNS_CONFIG_DIR", "/config/reticulum")


@dataclass
class _Bridge:
    mode: str
    service: str
    identity: str
    tcp: str
    target: str | None = None


@dataclass
class _Vpn:
    mode: str
    identity: str
    extra_args: list[str]


def _parse_bridges(doc: dict) -> list:
    out = []
    for i, entry in enumerate(doc.get("bridges", [])):
        mode = entry.get("mode")
        if mode not in ("listen", "connect"):
            sys.exit(f"bridges[{i}].mode must be 'listen' or 'connect', got {mode!r}")
        if mode == "connect" and not entry.get("target"):
            sys.exit(f"bridges[{i}] is connect-mode but has no 'target'")
        out.append(
            _Bridge(
                mode=mode,
                service=entry.get("service", "generic"),
                identity=entry["identity"],
                tcp=entry["tcp"],
                target=entry.get("target"),
            )
        )
    return out


def _parse_vpn(doc: dict) -> list:
    out = []
    for i, entry in enumerate(doc.get("vpn", [])):
        mode = entry.get("mode")
        if mode not in ("server", "client"):
            sys.exit(f"vpn[{i}].mode must be 'server' or 'client', got {mode!r}")
        extras: list[str] = []
        for key in ("tun", "subnet", "uplink", "mtu", "target"):
            value = entry.get(key)
            if value is not None:
                extras += [f"--{key}", str(value)]
        out.append(_Vpn(mode=mode, identity=entry["identity"], extra_args=extras))
    return out


def _spawn_bridge(spec: _Bridge) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "rns_tcp_bridge",
        "--config",
        RNS_CONFIG_DIR,
        spec.mode,
        "--identity",
        spec.identity,
        "--service",
        spec.service,
        "--tcp",
        spec.tcp,
    ]
    if spec.target:
        cmd += ["--target", spec.target]
    print(f"[supervisor] spawning bridge {spec.mode}/{spec.service}", flush=True)
    return subprocess.Popen(cmd)


def _spawn_vpn(spec: _Vpn) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "bridges.vpn",
        "--config",
        RNS_CONFIG_DIR,
        spec.mode,
        "--identity",
        spec.identity,
        *spec.extra_args,
    ]
    print(f"[supervisor] spawning vpn/{spec.mode}", flush=True)
    return subprocess.Popen(cmd)


def load(path: str) -> list:
    with open(path) as fh:
        doc = yaml.safe_load(fh) or {}
    return _parse_bridges(doc) + _parse_vpn(doc)


def spawn(spec) -> subprocess.Popen:
    if isinstance(spec, _Bridge):
        return _spawn_bridge(spec)
    if isinstance(spec, _Vpn):
        return _spawn_vpn(spec)
    raise TypeError(f"unknown spec type {type(spec).__name__}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="supervisor")
    parser.add_argument("config", help="path to bridges.yaml")
    args = parser.parse_args()
    specs = load(args.config)
    if not specs:
        print("[supervisor] nothing to run, exiting", flush=True)
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
            if entry["proc"].poll() is None:
                continue
            if entry["next"] == 0.0:
                delay = RESTART_BACKOFF[min(entry["fails"], len(RESTART_BACKOFF) - 1)]
                entry["fails"] += 1
                entry["next"] = time.time() + delay
                print(
                    f"[supervisor] {type(entry['spec']).__name__} exited "
                    f"(rc={entry['proc'].returncode}); restart in {delay}s",
                    flush=True,
                )
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
