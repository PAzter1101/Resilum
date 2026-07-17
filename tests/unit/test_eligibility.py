from rns_tcp_bridge.connect.candidates import Candidate
from rns_tcp_bridge.connect.eligibility import eligible


def _c(service, dest, country="*", healthy=True):
    return Candidate(
        dest_hash=dest, service=service, exit_country=country, healthy=healthy
    )


SKIPS = {"socks-egress": {b"own-se"}, "tor": {b"own-tor"}, "i2p": {b"own-i2p"}}


def test_smart_socks_egress_excludes_own_but_keeps_others():
    cands = [_c("socks-egress", b"own-se"), _c("socks-egress", b"other-se")]
    out = eligible(cands, "smart", [], [], SKIPS)
    assert {c.dest_hash for c in out} == {b"other-se"}


def test_smart_tor_keeps_own_and_others():
    cands = [_c("tor", b"own-tor"), _c("tor", b"other-tor")]
    out = eligible(cands, "smart", [], [], SKIPS)
    assert {c.dest_hash for c in out} == {b"own-tor", b"other-tor"}


def test_use_own_false_drops_all_own():
    cands = [_c("tor", b"own-tor"), _c("tor", b"other-tor")]
    out = eligible(cands, "false", [], [], SKIPS)
    assert {c.dest_hash for c in out} == {b"other-tor"}


def test_deny_country_excludes_matching_and_unknown():
    cands = [
        _c("socks-egress", b"a", "CN"),
        _c("socks-egress", b"b", "DE"),
        _c("tor", b"c", "*"),
    ]
    out = eligible(cands, "true", [], ["CN"], SKIPS)
    assert {c.dest_hash for c in out} == {
        b"b"
    }  # CN denied, "*" excluded under active filter


def test_allow_country_requires_membership_and_excludes_unknown():
    cands = [
        _c("socks-egress", b"a", "NL"),
        _c("socks-egress", b"b", "DE"),
        _c("tor", b"c", "*"),
    ]
    out = eligible(cands, "true", ["NL"], [], SKIPS)
    assert {c.dest_hash for c in out} == {b"a"}


def test_no_country_filter_keeps_unknown():
    cands = [_c("tor", b"c", "*")]
    out = eligible(cands, "true", [], [], SKIPS)
    assert {c.dest_hash for c in out} == {b"c"}


def test_unhealthy_excluded():
    cands = [_c("tor", b"c", healthy=False)]
    assert eligible(cands, "true", [], [], SKIPS) == []


def test_use_own_true_keeps_own_socks_egress():
    cands = [_c("socks-egress", b"own-se"), _c("socks-egress", b"other-se")]
    out = eligible(cands, "true", [], [], SKIPS)
    assert {c.dest_hash for c in out} == {b"own-se", b"other-se"}


def test_smart_keeps_own_i2p():
    cands = [_c("i2p", b"own-i2p"), _c("i2p", b"other-i2p")]
    out = eligible(cands, "smart", [], [], SKIPS)
    assert {c.dest_hash for c in out} == {b"own-i2p", b"other-i2p"}
