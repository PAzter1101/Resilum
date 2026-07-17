from rns_tcp_bridge.connect.candidates import Candidate
from rns_tcp_bridge.connect.selector import choose_best


def _c(dest, link=None, egress=None):
    c = Candidate(dest_hash=dest, service="tor")
    c.link_rtt = link
    c.egress_side = egress
    return c


def test_picks_min_effective_latency():
    a = _c(b"a", 0.01, 0.02)  # 0.03
    b = _c(b"b", 0.01, 0.50)  # 0.51
    assert choose_best([a, b], current=None).dest_hash == b"a"


def test_unmeasured_ranked_last():
    measured = _c(b"m", 0.01, 0.50)
    unmeasured = _c(b"u")  # effective None
    assert choose_best([unmeasured, measured], current=None).dest_hash == b"m"


def test_all_unmeasured_returns_one():
    u = _c(b"u")
    assert choose_best([u], current=None) is u


def test_hysteresis_keeps_current_on_small_gain():
    cur = _c(b"cur", 0.05, 0.05)  # 0.10
    challenger = _c(b"new", 0.045, 0.05)  # 0.095 -> only 5ms / 5% better
    assert choose_best([cur, challenger], current=cur).dest_hash == b"cur"


def test_hysteresis_switches_on_large_gain():
    cur = _c(b"cur", 0.05, 0.05)  # 0.10
    challenger = _c(b"new", 0.02, 0.02)  # 0.04 -> 60ms / 60% better
    assert choose_best([cur, challenger], current=cur).dest_hash == b"new"


def test_switches_when_current_no_longer_eligible():
    cur = _c(b"cur", 0.05, 0.05)
    other = _c(b"o", 0.09, 0.05)
    # current not in the eligible list -> must switch even without margin
    assert choose_best([other], current=cur).dest_hash == b"o"


def test_empty_returns_none():
    assert choose_best([], current=None) is None


def test_own_tor_zero_link_rtt_does_not_beat_fast_socks_egress():
    # own local Tor: link_rtt~0 but big egress_side (Tor circuit) -> effective ~0.35
    own_tor = _c(b"own-tor", 0.0, 0.35)
    fast_se = _c(b"se", 0.04, 0.01)  # remote socks-egress -> effective 0.05
    assert choose_best([own_tor, fast_se], current=None).dest_hash == b"se"


def test_keeps_current_when_it_is_the_fastest():
    cur = _c(b"cur", 0.01, 0.02)
    slower = _c(b"s", 0.05, 0.05)
    assert choose_best([cur, slower], current=cur).dest_hash == b"cur"
