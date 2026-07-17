import pytest

pytest.importorskip("RNS", reason="Reticulum (rns) not installed")

from rns_tcp_bridge import announce_payload
from rns_tcp_bridge.connect.announce import _make_registry_handler
from rns_tcp_bridge.connect.candidates import CandidateRegistry


class _FakeAnnounce:
    def __init__(self, country="DE", caps=()):
        self.exit_country = country
        self.capabilities = caps


def test_handler_upserts_candidate_with_metadata(monkeypatch):
    monkeypatch.setattr(
        announce_payload, "parse", lambda raw: _FakeAnnounce("NL", ("x",))
    )
    reg = CandidateRegistry()
    h = _make_registry_handler("tor", ["resilum", "discovery", "tor"], set(), reg)
    h.received_announce(b"peer", None, b"{}")
    cands = reg.for_service("tor")
    assert (
        len(cands) == 1
        and cands[0].exit_country == "NL"
        and cands[0].capabilities == ("x",)
    )


def test_handler_skips_self(monkeypatch):
    monkeypatch.setattr(announce_payload, "parse", lambda raw: _FakeAnnounce())
    reg = CandidateRegistry()
    h = _make_registry_handler("tor", ["a"], {b"me"}, reg)
    h.received_announce(b"me", None, b"{}")
    assert reg.for_service("tor") == []


def test_handler_removes_on_bad_payload(monkeypatch):
    monkeypatch.setattr(announce_payload, "parse", lambda raw: None)
    reg = CandidateRegistry()
    reg.upsert("tor", b"peer")
    h = _make_registry_handler("tor", ["a"], set(), reg)
    h.received_announce(b"peer", None, b"garbage")
    assert reg.for_service("tor") == []
