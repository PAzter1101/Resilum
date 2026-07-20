from covert import nftguard


def _record(monkeypatch):
    calls = []

    def fake_nft(*args):
        calls.append(args)
        return True

    monkeypatch.setattr(nftguard, "_nft", fake_nft)
    monkeypatch.setattr(nftguard.atexit, "register", lambda _fn: None)
    return calls


def test_install_adds_table_chain_and_both_rules(monkeypatch):
    calls = _record(monkeypatch)
    assert nftguard.install(0x1234) is True
    joined = [" ".join(a) for a in calls]
    assert any("add table inet resilum_covert" in c for c in joined)
    assert any("icmp id 4660 drop" in c for c in joined)
    assert any("icmpv6 id 4660 drop" in c for c in joined)


def test_install_reports_failure(monkeypatch):
    monkeypatch.setattr(nftguard, "_nft", lambda *args: False)
    monkeypatch.setattr(nftguard.atexit, "register", lambda _fn: None)
    assert nftguard.install(0x1234) is False


def test_remove_deletes_table(monkeypatch):
    calls = _record(monkeypatch)
    nftguard.remove()
    assert calls[-1] == ("delete", "table", "inet", "resilum_covert")
