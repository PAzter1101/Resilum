"""Parse and model the supervisor's YAML config.

Two component families are recognised: ``bridges:`` (rns_tcp_bridge
listen|connect) and ``vpn:`` (bridges.vpn server|client). Adding a new
family is one extra dataclass + parser here plus one ``_spawn_*`` in
bridge_spawn."""

import os
import re
import sys
from dataclasses import dataclass, field

import yaml

# ${VAR} or ${VAR:-default}. Anything else passes through untouched.
_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")


def _expand_env(text: str) -> str:
    def sub(match: re.Match) -> str:
        name, default = match.group(1), match.group(2)
        return os.environ.get(name, default if default is not None else "")

    return _ENV_VAR_PATTERN.sub(sub, text)


@dataclass
class _Bridge:
    mode: str
    services: list[str]
    identity: str
    tcp: str
    target: str | None = None
    use_own: str = "smart"
    allow_countries: list[str] = field(default_factory=list)
    deny_countries: list[str] = field(default_factory=list)
    probe_targets: list[str] = field(default_factory=list)
    exit_country: str = "*"


@dataclass
class _Vpn:
    mode: str
    identity: str
    extra_args: list[str]


def _services_of(entry: dict) -> list[str]:
    """Accept either ``service: foo`` (single, legacy) or
    ``services: [a, b]`` (priority list, connect-mode fallback chain).
    Single service stays single-element list for symmetry."""
    if "services" in entry:
        services = entry["services"]
        if not isinstance(services, list) or not services:
            raise SystemExit(
                f"bridges entry {entry!r} has empty or non-list `services`"
            )
        return [str(s) for s in services]
    return [str(entry.get("service", "generic"))]


def _parse_bridges(doc: dict) -> list:
    out = []
    for i, entry in enumerate(doc.get("bridges", [])):
        mode = entry.get("mode")
        if mode not in ("listen", "connect"):
            sys.exit(f"bridges[{i}].mode must be 'listen' or 'connect', got {mode!r}")
        services = _services_of(entry)
        if mode == "listen" and len(services) != 1:
            sys.exit(
                f"bridges[{i}] is listen-mode but has {len(services)} services; "
                "listen-mode wraps exactly one service"
            )
        out.append(
            _Bridge(
                mode=mode,
                services=services,
                identity=entry["identity"],
                tcp=entry["tcp"],
                target=entry.get("target"),
                use_own=str(entry.get("use_own", "smart")),
                allow_countries=[str(c) for c in entry.get("allow_countries", [])],
                deny_countries=[str(c) for c in entry.get("deny_countries", [])],
                probe_targets=[str(t) for t in entry.get("probe_targets", [])],
                exit_country=str(entry.get("exit_country", "*")),
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


def load(path: str) -> list:
    with open(path) as fh:
        raw = fh.read()
    doc = yaml.safe_load(_expand_env(raw)) or {}
    return _parse_bridges(doc) + _parse_vpn(doc)


def _siblings_for(spec: _Bridge, all_specs: list) -> list[str]:
    """Identity-file paths of all listen-mode bridges whose (single)
    service is in ``spec``'s service list — these are the announces
    that ``spec`` (if it is connect-mode) should treat as its own and
    skip during auto-discovery."""
    spec_services = set(spec.services)
    return [
        s.identity
        for s in all_specs
        if isinstance(s, _Bridge)
        and s.mode == "listen"
        and any(svc in spec_services for svc in s.services)
    ]
