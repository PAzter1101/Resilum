"""Translate parsed specs into child processes. Each ``_spawn_*`` builds
the argv for one component family; ``spawn`` dispatches on spec type."""

import os
import subprocess
import sys

from bridge_config import _Bridge, _Covert, _siblings_for, _Vpn
from log_setup import get_logger

log = get_logger("supervisor")

RNS_CONFIG_DIR = os.environ.get("RNS_CONFIG_DIR", "/config/reticulum")


def _spawn_bridge(
    spec: _Bridge, sibling_listen_identities: list[str]
) -> subprocess.Popen:
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
        "--tcp",
        spec.tcp,
    ]
    for service in spec.services:
        cmd += ["--service", service]
    if spec.target:
        cmd += ["--target", spec.target]
    if spec.mode == "connect" and not spec.target:
        for path in sibling_listen_identities:
            cmd += ["--skip-self-identity", path]
    if spec.mode == "connect":
        cmd += ["--use-own", spec.use_own]
        for cc in spec.allow_countries:
            cmd += ["--allow-country", cc]
        for cc in spec.deny_countries:
            cmd += ["--deny-country", cc]
        for target in spec.probe_targets:
            cmd += ["--probe-target", target]
    if spec.mode == "listen" and spec.exit_country != "*":
        cmd += ["--exit-country", spec.exit_country]
    label = "+".join(spec.services)
    log.info("spawning bridge %s/%s", spec.mode, label)
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
    log.info("spawning vpn/%s", spec.mode)
    return subprocess.Popen(cmd)


def _spawn_covert(spec: _Covert) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "covert.discovery",
        spec.carrier,
        "--role",
        spec.role,
        "--identity",
        spec.identity,
        "--config",
        RNS_CONFIG_DIR,
    ]
    for addr in spec.addresses:
        cmd += ["--address", addr]
    if spec.interface:
        cmd += ["--interface", spec.interface]
    if spec.mtu != 1400:
        cmd += ["--mtu", str(spec.mtu)]
    if spec.bitrate != 32000:
        cmd += ["--bitrate", str(spec.bitrate)]
    log.info("spawning covert/%s", spec.carrier)
    return subprocess.Popen(cmd)


def spawn(spec, all_specs: list) -> subprocess.Popen:
    if isinstance(spec, _Bridge):
        return _spawn_bridge(spec, _siblings_for(spec, all_specs))
    if isinstance(spec, _Vpn):
        return _spawn_vpn(spec)
    if isinstance(spec, _Covert):
        return _spawn_covert(spec)
    raise TypeError(f"unknown spec type {type(spec).__name__}")
