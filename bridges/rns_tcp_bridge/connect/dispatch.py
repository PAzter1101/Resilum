"""Outbound dispatcher: take an accepted client TCP socket and try
each service in priority order until one yields a working RNS Link
to a peer's listen-bridge.

The first service that produces an active Link wins; the pump is
wired and the loop returns. If every service in the chain fails, the
socket is closed."""

import time

import RNS

from ..constants import DEFAULT_ASPECTS, LINK_ESTABLISH_TIMEOUT, PATH_REQUEST_TIMEOUT
from ..pump import wire_link_to_socket
from .link_registry import _register_link


def _resolve_target(target_hash, aspects):
    """Return an OUT-direction destination for ``target_hash``, kicking
    off a path-request and waiting up to ``PATH_REQUEST_TIMEOUT``."""
    if not RNS.Transport.has_path(target_hash):
        RNS.Transport.request_path(target_hash)
        deadline = time.time() + PATH_REQUEST_TIMEOUT
        while time.time() < deadline and not RNS.Transport.has_path(target_hash):
            time.sleep(0.1)

    if not RNS.Transport.has_path(target_hash):
        return None

    remote_identity = RNS.Identity.recall(target_hash)
    if remote_identity is None:
        return None

    return RNS.Destination(
        remote_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        *aspects,
    )


def _open_link(target_dest, target_hash):
    link = RNS.Link(target_dest)
    deadline = time.time() + LINK_ESTABLISH_TIMEOUT
    while time.time() < deadline and link.status != RNS.Link.ACTIVE:
        time.sleep(0.1)
    if link.status != RNS.Link.ACTIVE:
        RNS.log(
            f"[bridge:connect] Link to {RNS.prettyhexrep(target_hash)} "
            f"did not become active in {LINK_ESTABLISH_TIMEOUT}s",
            RNS.LOG_WARNING,
        )
        link.teardown()
        return None
    return link


def _try_one_service(sock, service: str, target_hash: bytes, aspects: list) -> bool:
    """Attempt to dispatch ``sock`` through one service's target. Returns
    True if the Link is up and the pump is wired (caller must NOT close
    the socket)."""
    pretty = RNS.prettyhexrep(target_hash)
    RNS.log(f"[bridge:connect/{service}] resolving {pretty}", RNS.LOG_VERBOSE)
    target_dest = _resolve_target(target_hash, aspects)
    if target_dest is None:
        RNS.log(
            f"[bridge:connect/{service}] no path to {pretty} "
            f"after {PATH_REQUEST_TIMEOUT}s",
            RNS.LOG_WARNING,
        )
        return False
    link = _open_link(target_dest, target_hash)
    if link is None:
        return False
    RNS.log(f"[bridge:connect/{service}] Link active, wiring TCP", RNS.LOG_VERBOSE)
    _register_link(target_hash, link)
    wire_link_to_socket(link, sock, label=f"connect/{service}")
    return True


def _handle_outbound(sock, services: list, targets, lock):
    """Try each service in priority order. On the first one that yields
    a working Link, hand the socket off to the pump and return. If all
    services fail, close the socket."""
    for service in services:
        with lock:
            target_hash = targets.get(service)
        if target_hash is None:
            RNS.log(
                f"[bridge:connect/{service}] no target known yet, skipping",
                RNS.LOG_DEBUG,
            )
            continue
        aspects = DEFAULT_ASPECTS + [service]
        if _try_one_service(sock, service, target_hash, aspects):
            return
    RNS.log(
        "[bridge:connect] no service in fallback chain yielded a Link, "
        "dropping TCP connection",
        RNS.LOG_WARNING,
    )
    sock.close()


def _wait_for_any_target(targets, lock, services, timeout):
    """Block until at least one of ``services`` has a target hash in the
    shared dict, or ``timeout`` elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with lock:
            if any(targets.get(s) is not None for s in services):
                return True
        time.sleep(0.5)
    return False
