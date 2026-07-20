"""Helper for adding manually-instantiated interfaces to the running
RNS Transport.

When Reticulum is configured through its YAML config the loader runs
each interface through ``RNS.Reticulum._add_interface``, which sets
nine bookkeeping attributes (`mode`, `OUT`, `ifac_size`,
`announce_cap`, `announce_rate_target/grace/penalty`, `ifac_netname`,
`ifac_netkey`). Some of those — notably ``announce_rate_target`` —
are read on every received packet by ``RNS.Transport``; if they are
missing, Transport raises ``AttributeError`` and tears the interface
down, only to re-instantiate it and crash the same way on the next
packet.

Discovery plugins build interfaces by hand from announce payloads
and originally appended them to ``RNS.Transport.interfaces`` raw. To
keep that path working with newer Reticulum, plugins now go through
:func:`register_in_transport`, which mirrors the attribute defaults
``_add_interface`` would have set.
"""

import RNS
from RNS.Interfaces.Interface import Interface

from rns_tcp_bridge.announce_cap import adaptive_cap


def register_in_transport(iface) -> None:
    iface.mode = Interface.MODE_FULL
    iface.OUT = True
    iface.optimise_mtu()
    iface.ifac_size = iface.DEFAULT_IFAC_SIZE
    iface.announce_cap = RNS.Reticulum.ANNOUNCE_CAP / 100.0
    iface.announce_rate_target = None
    iface.announce_rate_grace = None
    iface.announce_rate_penalty = None
    iface.ifac_netname = None
    iface.ifac_netkey = None
    RNS.Transport.interfaces.append(iface)
    adaptive_cap(iface)
