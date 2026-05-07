"""Verify the discovery_plugins helper sets every attribute that
RNS.Reticulum._add_interface would have set, so manually-instantiated
interfaces don't crash Transport on the first packet."""

from unittest import mock

import pytest

pytest.importorskip("RNS", reason="Reticulum (rns) not installed")

import RNS

from rns_tcp_bridge.discovery_plugins import _transport


def _fake_interface():
    """Stand-in for an Interface subclass: real attributes (DEFAULT_IFAC_SIZE,
    optimise_mtu) accessed by the helper, the rest set freely."""
    iface = mock.MagicMock()
    iface.DEFAULT_IFAC_SIZE = 16
    return iface


def test_register_sets_every_attr_add_interface_would_set():
    iface = _fake_interface()
    fake_transport_list: list = []
    with mock.patch.object(RNS.Transport, "interfaces", fake_transport_list):
        _transport.register_in_transport(iface)

    iface.optimise_mtu.assert_called_once_with()
    assert iface.OUT is True
    assert iface.mode == _transport.Interface.MODE_FULL
    assert iface.ifac_size == 16
    assert iface.announce_cap == RNS.Reticulum.ANNOUNCE_CAP / 100.0
    assert iface.announce_rate_target is None
    assert iface.announce_rate_grace is None
    assert iface.announce_rate_penalty is None
    assert iface.ifac_netname is None
    assert iface.ifac_netkey is None
    assert fake_transport_list == [iface]
