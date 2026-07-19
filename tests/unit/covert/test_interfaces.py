import sys

from covert.interfaces import client_interface_config, server_interface_config


def test_client_config_embeds_pubkey_hex():
    cfg = client_interface_config("icmp", "203.0.113.9", "deadbeef")
    assert cfg["name"] == "CovertDiscovered[icmp:203.0.113.9]"
    assert cfg["respawn_delay"] == 5
    assert cfg["command"] == (
        f"{sys.executable} -m covert icmp client "
        "--dst 203.0.113.9 --server-identity deadbeef"
    )


def test_client_config_appends_interface():
    cfg = client_interface_config("icmp", "203.0.113.9", "deadbeef", "eth1")
    assert cfg["command"].endswith("--interface eth1")


def test_client_config_appends_non_default_mtu():
    cfg = client_interface_config("icmp", "203.0.113.9", "deadbeef", "eth1", 1280)
    assert cfg["command"].endswith("--interface eth1 --mtu 1280")


def test_config_omits_default_mtu():
    cfg = client_interface_config("icmp", "203.0.113.9", "deadbeef")
    assert "--mtu" not in cfg["command"]


def test_server_config_appends_interface():
    cfg = server_interface_config("icmp", "/config/covert/server.id", "eth0")
    assert cfg["command"] == (
        f"{sys.executable} -m covert icmp server "
        "--identity /config/covert/server.id --interface eth0"
    )
    assert cfg["name"] == "CovertServer[icmp]"
