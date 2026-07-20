from rns_tcp_bridge.connect.candidates import Candidate, CandidateRegistry


def test_effective_latency_none_until_both_measured():
    c = Candidate(dest_hash=b"\x01", service="tor")
    assert c.effective_latency is None
    c.link_rtt = 0.05
    assert c.effective_latency is None  # egress_side still unknown
    c.egress_side = 0.30
    assert abs(c.effective_latency - 0.35) < 1e-9


def test_registry_upsert_updates_not_duplicates():
    reg = CandidateRegistry()
    a = reg.upsert("tor", b"\x01", exit_country="DE")
    b = reg.upsert("tor", b"\x01", exit_country="NL", capabilities=("x",))
    assert a is b  # same candidate object, updated in place
    assert b.exit_country == "NL"
    assert b.capabilities == ("x",)
    assert len(reg.for_service("tor")) == 1


def test_registry_all_flattens_services():
    reg = CandidateRegistry()
    reg.upsert("tor", b"\x01")
    reg.upsert("i2p", b"\x02")
    assert {c.dest_hash for c in reg.all()} == {b"\x01", b"\x02"}


def test_registry_remove():
    reg = CandidateRegistry()
    reg.upsert("tor", b"\x01")
    reg.remove("tor", b"\x01")
    assert reg.for_service("tor") == []
