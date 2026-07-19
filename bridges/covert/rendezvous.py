"""Fetch a covert server's endpoint over an encrypted RNS link instead of from
the broadcast announce, so the real address is disclosed only to a peer that
reaches the server over the mesh — never published to everyone."""

import threading
import time

import RNS

from .endpoint import parse_endpoint

ENDPOINT_PATH = "endpoint"
_LINK_TIMEOUT = 15.0


def endpoint_responder(endpoint: bytes):
    """Serve a fixed endpoint blob. RNS dispatches request handlers by parameter
    count (5 or 6) and rejects any other signature, so this needs five explicit
    params rather than *args."""

    def _respond(path, data, request_id, remote_identity, requested_at):
        return endpoint

    return _respond


def request_endpoint(announced_identity, carrier: str):
    """Open a link to the announced covert-discovery destination, request its
    endpoint, and return the address CSV (or None on failure/timeout)."""
    dest = RNS.Destination(
        announced_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        "resilum",
        "discovery",
        f"covert_{carrier}",
    )
    link = RNS.Link(dest)
    deadline = time.time() + _LINK_TIMEOUT
    while time.time() < deadline and link.status != RNS.Link.ACTIVE:
        time.sleep(0.1)
    if link.status != RNS.Link.ACTIVE:
        link.teardown()
        return None

    done = threading.Event()
    box: dict = {}

    def _on_response(receipt):
        box["raw"] = receipt.response
        done.set()

    link.request(
        ENDPOINT_PATH,
        response_callback=_on_response,
        failed_callback=lambda _r: done.set(),
        timeout=_LINK_TIMEOUT,
    )
    done.wait(_LINK_TIMEOUT + 2)
    link.teardown()

    ep = parse_endpoint(box["raw"]) if box.get("raw") else None
    return ep[1] if ep and ep[0] == carrier and ep[1] else None
