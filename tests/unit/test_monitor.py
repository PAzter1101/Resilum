from rns_tcp_bridge.connect import monitor
from rns_tcp_bridge.connect.candidates import Candidate


def _c(dest, link=None, egress=None, probe=None):
    c = Candidate(dest_hash=dest, service="tor")
    c.link_rtt = link
    c.egress_side = egress
    c.last_probe = probe
    return c


def test_egress_side_from_probe_subtracts_link_rtt():
    assert abs(monitor.egress_side_from_probe(e2e=0.40, link_rtt=0.05) - 0.35) < 1e-9


def test_egress_side_floors_at_zero():
    # noise can make e2e < link_rtt momentarily; never go negative
    assert monitor.egress_side_from_probe(e2e=0.04, link_rtt=0.05) == 0.0


def test_top_k_prefers_measured_then_unmeasured():
    a = _c(b"a", 0.01, 0.02)  # 0.03
    b = _c(b"b", 0.01, 0.90)  # 0.91
    u = _c(b"u")  # unmeasured
    top = monitor.top_k([b, u, a], k=2)
    assert [c.dest_hash for c in top] == [b"a", b"b"]


def test_due_for_probe_true_when_never_probed():
    assert monitor.due_for_probe(_c(b"a"), now=100.0, interval=60.0) is True


def test_due_for_probe_false_when_recent():
    assert (
        monitor.due_for_probe(_c(b"a", probe=100.0), now=130.0, interval=60.0) is False
    )


def test_due_for_probe_true_when_stale():
    assert (
        monitor.due_for_probe(_c(b"a", probe=100.0), now=170.0, interval=60.0) is True
    )
