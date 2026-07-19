"""Parse and validate the supervisor's YAML config into the bridge_models
families. Adding a new family is one extra model in bridge_models plus a parser
here and one ``_spawn_*`` in bridge_spawn."""

import os
import re
import sys

import yaml
from pydantic import ValidationError

from bridge_models import _Bridge, _Covert, _Vpn

# ${VAR} or ${VAR:-default}. Anything else passes through untouched.
_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")


def _expand_env(text: str) -> str:
    def sub(match: re.Match) -> str:
        name, default = match.group(1), match.group(2)
        return os.environ.get(name, default if default is not None else "")

    return _ENV_VAR_PATTERN.sub(sub, text)


def _services_of(entry: dict) -> list[str]:
    """Accept either ``service: foo`` (single, legacy) or
    ``services: [a, b]`` (priority list, connect-mode fallback chain).
    Single service stays single-element list for symmetry."""
    if "services" in entry:
        services = entry["services"]
        if not isinstance(services, list) or not services:
            sys.exit(f"bridges entry {entry!r} has empty or non-list `services`")
        return [str(s) for s in services]
    return [str(entry.get("service", "generic"))]


def _addresses_of(entry: dict) -> list[str]:
    """Accept a YAML list, a single scalar, or a comma-separated string (the
    shape ``${RESILUM_COVERT_ADDR}`` expands to). Empty/unset yields []."""
    raw = entry.get("addresses", entry.get("address"))
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(a).strip() for a in raw if str(a).strip()]
    return [a.strip() for a in str(raw).split(",") if a.strip()]


def _abort(ctx: str, exc: ValidationError):
    err = exc.errors()[0]
    loc = ".".join(str(x) for x in err["loc"]) or "?"
    sys.exit(f"{ctx}: {loc}: {err['msg']}")


def _parse_bridges(doc: dict) -> list:
    out = []
    for i, entry in enumerate(doc.get("bridges", [])):
        ctx = f"bridges[{i}]"
        services = _services_of(entry)
        if entry.get("mode") == "listen" and len(services) != 1:
            sys.exit(
                f"{ctx} is listen-mode but has {len(services)} services; "
                "listen-mode wraps exactly one service"
            )
        try:
            out.append(
                _Bridge.model_validate(
                    {
                        "mode": entry.get("mode"),
                        "services": services,
                        "identity": entry.get("identity"),
                        "tcp": entry.get("tcp"),
                        "target": entry.get("target"),
                        "use_own": str(entry.get("use_own", "smart")),
                        "allow_countries": [
                            str(c) for c in entry.get("allow_countries", [])
                        ],
                        "deny_countries": [
                            str(c) for c in entry.get("deny_countries", [])
                        ],
                        "probe_targets": [
                            str(t) for t in entry.get("probe_targets", [])
                        ],
                        "exit_country": str(entry.get("exit_country", "*")),
                    }
                )
            )
        except ValidationError as exc:
            _abort(ctx, exc)
    return out


def _parse_vpn(doc: dict) -> list:
    out = []
    for i, entry in enumerate(doc.get("vpn", [])):
        ctx = f"vpn[{i}]"
        try:
            out.append(
                _Vpn.model_validate(
                    {
                        "mode": entry.get("mode"),
                        "identity": entry.get("identity"),
                        "tun": entry.get("tun"),
                        "subnet": entry.get("subnet"),
                        "uplink": entry.get("uplink"),
                        "mtu": entry.get("mtu"),
                        "target": entry.get("target"),
                    }
                )
            )
        except ValidationError as exc:
            _abort(ctx, exc)
    return out


def _parse_covert(doc: dict) -> list:
    out = []
    for i, entry in enumerate(doc.get("covert", [])):
        ctx = f"covert[{i}]"
        if not entry.get("carrier"):
            sys.exit(f"{ctx}: missing carrier")
        try:
            out.append(
                _Covert.model_validate(
                    {
                        "carrier": str(entry["carrier"]),
                        "role": str(entry.get("role") or "both"),
                        "addresses": _addresses_of(entry),
                        "interface": str(entry.get("interface") or ""),
                        "mtu": entry.get("mtu") or 1400,
                        "identity": str(entry.get("identity") or ""),
                    }
                )
            )
        except ValidationError as exc:
            _abort(ctx, exc)
    return out


def load(path: str) -> list:
    with open(path) as fh:
        raw = fh.read()
    doc = yaml.safe_load(_expand_env(raw)) or {}
    return _parse_bridges(doc) + _parse_vpn(doc) + _parse_covert(doc)


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
