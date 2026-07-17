"""Verify SocksTCPClientInterface picks the SOCKS dispatch path only
when the configuration carries socks_proxy_host/port, and falls back
to the plain TCP path otherwise. Both paths are stubbed — no network."""

import sys
import types
from unittest import mock

import pytest

if "RNS" not in sys.modules:
    pytest.importorskip("RNS", reason="Reticulum (rns) not installed")
if "socks" not in sys.modules:
    pytest.importorskip("socks", reason="PySocks not installed")

from RNS.Interfaces.Interface import Interface

from socks_tcp_interface import SocksTCPClientInterface


@pytest.fixture
def patched_parent():
    """Stub out TCPClientInterface.__init__ so we can construct the
    subclass without actually opening sockets or starting threads."""
    target = "RNS.Interfaces.TCPInterface.TCPClientInterface.__init__"

    def stub(self, owner, configuration, connected_socket=None):
        c = Interface.get_config_obj(configuration)
        self.target_ip = c.get("target_host")
        self.target_port = int(c["target_port"])
        self.socket = None
        self.online = False
        self.writing = False
        self.never_connected = True
        self.name = c.get("name", "test")
        self.i2p_tunneled = False

    with mock.patch(target, stub):
        yield


def test_falls_back_when_no_socks_config(patched_parent):
    iface = SocksTCPClientInterface(
        owner=None,
        configuration={
            "name": "no-socks",
            "target_host": "203.0.113.1",
            "target_port": "4242",
        },
    )
    assert iface._socks_host is None
    assert iface._socks_port is None

    parent_called = {}

    def fake_super_connect(self, initial=False):
        parent_called["yes"] = True
        return True

    with mock.patch(
        "RNS.Interfaces.TCPInterface.TCPClientInterface.connect",
        fake_super_connect,
    ):
        assert iface.connect(initial=True) is True

    assert parent_called == {"yes": True}


def test_uses_socks_when_configured(patched_parent):
    iface = SocksTCPClientInterface(
        owner=None,
        configuration={
            "name": "socks",
            "target_host": "abc123.onion",
            "target_port": "4242",
            "socks_proxy_host": "127.0.0.1",
            "socks_proxy_port": "9050",
        },
    )
    assert iface._socks_host == "127.0.0.1"
    assert iface._socks_port == 9050

    fake_sock = mock.MagicMock()
    fake_sock_module = types.SimpleNamespace(
        SOCKS5=2,
        socksocket=mock.MagicMock(return_value=fake_sock),
    )

    with (
        mock.patch.dict(sys.modules, {"socks": fake_sock_module}),
        mock.patch("socks_tcp_interface.socks", fake_sock_module),
    ):
        assert iface.connect(initial=True) is True

    fake_sock_module.socksocket.assert_called_once_with()
    fake_sock.set_proxy.assert_called_once_with(2, "127.0.0.1", 9050, rdns=True)
    fake_sock.connect.assert_called_once_with(("abc123.onion", 4242))
    assert iface.socket is fake_sock
    assert iface.online is True
