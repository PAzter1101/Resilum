from covert import netdetect


def test_public_ip_resolves(monkeypatch):
    monkeypatch.setattr(netdetect, "_iface_ip", lambda iface: "1.1.1.1")
    assert netdetect.detect_address() == "1.1.1.1"


def test_private_ip_yields_empty(monkeypatch):
    monkeypatch.setattr(netdetect, "_iface_ip", lambda iface: "10.0.0.2")
    assert netdetect.detect_address() == ""


def test_unassigned_iface_yields_empty(monkeypatch):
    monkeypatch.setattr(netdetect, "_iface_ip", lambda iface: "0.0.0.0")
    assert netdetect.detect_address("eth9") == ""


def test_public_v6_resolves(monkeypatch):
    monkeypatch.setattr(netdetect, "_iface_ip", lambda iface: "2606:4700:4700::1111")
    assert netdetect.detect_address() == "2606:4700:4700::1111"


def test_documentation_range_is_not_public(monkeypatch):
    monkeypatch.setattr(netdetect, "_iface_ip", lambda iface: "198.51.100.7")
    assert netdetect.detect_address() == ""
