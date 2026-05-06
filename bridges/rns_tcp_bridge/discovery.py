"""Generic announce / discover loop for any transport plugin.

One process per `mode: listen` bridge. Symmetric by design: the same
loop announces the local node's endpoint and reacts to remote
announces — no separate `announce-only` or `discover-only` modes
exist (see project memory `feedback_resilum_p2p_symmetry`)."""

import threading
import time
from typing import Optional

import RNS

from . import announce_trigger, cache
from .constants import ANNOUNCE_INTERVAL_SECONDS
from .discovery_plugins import DiscoveryPlugin
from .discovery_plugins import load as load_plugin

ASPECT_PREFIX = ["resilum", "discovery"]
TTL_SECONDS = 24 * 60 * 60
TOP_N_ACTIVE = 10
PRUNE_INTERVAL_SECONDS = 60 * 60


class _AnnounceHandler:
    def __init__(self, service: str, plugin: DiscoveryPlugin, cache_path: str):
        self.aspect_filter = ".".join(ASPECT_PREFIX + [service])
        self.receive_path_responses = False
        self.service = service
        self.plugin = plugin
        self.cache_path = cache_path

    def received_announce(self, destination_hash, announced_identity, app_data):
        if not app_data:
            return
        records = cache.load(self.cache_path)
        cache.upsert(records, app_data)
        cache.save(self.cache_path, records)
        try:
            self.plugin.consume_endpoint(app_data)
        except Exception as exc:
            RNS.log(
                f"[discovery:{self.service}] consume failed: {exc}", RNS.LOG_WARNING
            )


def _restore_top_n(plugin: DiscoveryPlugin, cache_path: str) -> None:
    records = cache.load(cache_path)
    cache.prune(records, TTL_SECONDS)
    cache.save(cache_path, records)
    for endpoint in cache.top_n(records, TOP_N_ACTIVE):
        try:
            plugin.consume_endpoint(endpoint)
        except Exception as exc:
            RNS.log(f"[discovery] warm-start consume failed: {exc}", RNS.LOG_DEBUG)


def _announce_loop(destination, plugin: DiscoveryPlugin, service: str) -> None:
    trigger = announce_trigger.register()
    while True:
        try:
            payload = plugin.produce_endpoint()
            destination.announce(app_data=payload)
            RNS.log(f"[discovery:{service}] announced {payload!r}", RNS.LOG_DEBUG)
        except Exception as exc:
            RNS.log(f"[discovery:{service}] announce skipped: {exc}", RNS.LOG_DEBUG)
        if trigger.wait(ANNOUNCE_INTERVAL_SECONDS):
            trigger.clear()


def _prune_loop(cache_path: str) -> None:
    while True:
        time.sleep(PRUNE_INTERVAL_SECONDS)
        records = cache.load(cache_path)
        if cache.prune(records, TTL_SECONDS):
            cache.save(cache_path, records)


def start(service: str, identity: RNS.Identity) -> Optional[DiscoveryPlugin]:
    """Bring up the announce + discover loops for `service`. Returns
    the loaded plugin, or None if the service has no plugin and the
    caller should silently disable discovery."""
    plugin = load_plugin(service)
    if plugin is None:
        return None

    cache_path = f"/config/discovered/{service}.json"
    aspects = ASPECT_PREFIX + [service]
    destination = RNS.Destination(
        identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        *aspects,
    )

    handler = _AnnounceHandler(service, plugin, cache_path)
    RNS.Transport.register_announce_handler(handler)

    _restore_top_n(plugin, cache_path)

    threading.Thread(
        target=_announce_loop,
        args=(destination, plugin, service),
        name=f"discovery-announce-{service}",
        daemon=True,
    ).start()
    threading.Thread(
        target=_prune_loop,
        args=(cache_path,),
        name=f"discovery-prune-{service}",
        daemon=True,
    ).start()

    RNS.log(
        f"[discovery:{service}] started "
        f"(aspect={'.'.join(aspects)}, top_n={TOP_N_ACTIVE})",
        RNS.LOG_INFO,
    )
    return plugin
