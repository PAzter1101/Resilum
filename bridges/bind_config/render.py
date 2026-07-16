"""Config-text rendering: Yggdrasil and Reticulum managed regions."""

from bind_config.parsing import parse_rns_listen, parse_ygg_listen
from bind_config.regions import replace_region


def render_ygg(text, value):
    uris = parse_ygg_listen(value)
    body = [f'    "{uri}"' for uri in uris]
    return replace_region(text, "ygg-public-listen", body)


def rns_block(name, host, port, discoverable):
    return [
        f"  [[{name}]]",
        "    type = TCPServerInterface",
        "    enabled = yes",
        f"    listen_ip = {host}",
        f"    listen_port = {port}",
        f"    discoverable = {'yes' if discoverable else 'no'}",
        "    discovery_name = resilum",
        "    mode = gateway",
    ]


def render_rns(text, value):
    binds = parse_rns_listen(value)
    body: list[str] = []
    for idx, (host, port) in enumerate(binds, 1):
        if body:
            body.append("")
        name = (
            "Public TCP listener" if len(binds) == 1 else f"Public TCP listener {idx}"
        )
        body.extend(rns_block(name, host, port, discoverable=(idx == 1)))
    return replace_region(text, "rns-public-listen", body)
